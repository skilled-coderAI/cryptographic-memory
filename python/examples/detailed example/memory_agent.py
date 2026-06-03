"""Shared cryptomem engine + an instrumented verified-memory pipeline.

This module is the brain behind the web view in ``server.py``. It owns a single
:class:`cryptomem.MemoryClient` (with semantic MiniLM embeddings when available)
and exposes :func:`run_pipeline`, which performs the verified-memory retrieval
*stage by stage* and reports every stage through an ``emit`` callback so the UI
can render exactly how a fact becomes a trusted answer:

    embed -> vector retrieval -> signature verification -> grounding gate
    -> (grounded) synthesize | (nothing verified) abstain

Nothing here is faked: similarities, signature checks, confidences, and the
Merkle ledger root all come straight from the engine.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from cryptomem import MemoryClient, Relationship

MIN_CONFIDENCE = float(os.environ.get("MEM_MIN_CONFIDENCE", "0.30"))
OLLAMA_HOST = os.environ.get("CRYPTOMEM_OLLAMA_URL", "http://localhost:11434")
MODEL_ID = os.environ.get("AGNO_MODEL", "qwen3.5:0.8b")
# KV-cache context window. Smaller = far less RAM, which matters a lot when a
# tiny model shares an 8 GB CPU box with the embedder.
NUM_CTX = int(os.environ.get("MEM_NUM_CTX", "2048"))
# Embedder: "stub" (zero-RAM, default) keeps memory free for the local model on
# small machines; set MEM_EMBEDDER=minilm for real semantic retrieval.
EMBEDDER_CHOICE = os.environ.get("MEM_EMBEDDER", "stub").lower()

Emit = Callable[[dict], None]

_MEM: MemoryClient | None = None
_EMBEDDER_LABEL = "stub"


def _build_embedder() -> Any:
    """Select the embedder: lightweight stub by default, MiniLM on request."""
    global _EMBEDDER_LABEL
    if EMBEDDER_CHOICE in ("minilm", "semantic", "local"):
        try:
            from cryptomem import MiniLMEmbedder

            embedder = MiniLMEmbedder()
            embedder.embed("warmup")  # surface download/offline errors up front
            _EMBEDDER_LABEL = "MiniLM (semantic, 384-dim)"
            return embedder
        except Exception as exc:  # noqa: BLE001 - intentional graceful fallback
            from cryptomem import StubEmbedder

            _EMBEDDER_LABEL = f"stub (MiniLM unavailable: {exc})"
            return StubEmbedder()

    from cryptomem import StubEmbedder

    _EMBEDDER_LABEL = "stub (hash-based, low-RAM)"
    return StubEmbedder()


def get_memory() -> MemoryClient:
    """Return the process-wide MemoryClient, seeding demo facts on first use."""
    global _MEM
    if _MEM is None:
        _MEM = MemoryClient(embedder=_build_embedder())
        _seed(_MEM)
    return _MEM


def embedder_label() -> str:
    return _EMBEDDER_LABEL


def _seed(mem: MemoryClient) -> None:
    """Seed a couple of signed, related facts (idempotent)."""
    if any(h.verified for h in mem.query("Project Phoenix budget", top_k=1)):
        return
    owner = mem.archive("Alice Chen", "Alice Chen is the finance lead for FY26.")
    mem.archive(
        "Project Phoenix",
        "Project Phoenix budget was approved at $4.2M for FY26.",
        relationships=[Relationship(type="approved_by", target_id=owner.node_id)],
        metadata={"source": "Q3-board-minutes.pdf"},
    )
    mem.archive(
        "Project Atlas",
        "Project Atlas shipped its v1 API to production on 2026-03-14.",
        metadata={"source": "release-notes.md"},
    )


def list_facts() -> list[dict]:
    """Return every stored, signature-verified fact for the sidebar."""
    mem = get_memory()
    facts = []
    for node in mem.store.all():
        verified = mem.verify(node)
        crypto = node.crypto
        facts.append(
            {
                "node_id": node.node_id,
                "entity": node.entity,
                "content": node.content,
                "verified": verified,
                "hash": (crypto.hash[:12] + "..") if crypto else None,
                "source": node.metadata.get("source"),
            }
        )
    return facts


def _short(text: str, n: int = 90) -> str:
    return text if len(text) <= n else text[: n - 1] + "\u2026"


def run_pipeline(query: str, emit: Emit) -> tuple[str, dict]:
    """Run the verified-memory pipeline, emitting a trace step per stage.

    Returns ``(facts_block, provenance)`` where ``facts_block`` is the string
    handed back to the LLM (the verified context, or a NO_VERIFIED_MEMORY
    abstention notice) and ``provenance`` summarises what grounded the answer.
    """
    mem = get_memory()

    # 1) Embed the query.
    vector = mem.embedder.embed(query)
    emit(
        {
            "type": "step",
            "stage": "embed",
            "title": "Embed query",
            "detail": f"{_EMBEDDER_LABEL} \u2192 {len(vector)}-dim vector",
        }
    )

    # 2) Vector retrieval over the signed store (raw cosine similarity).
    candidates = mem.store.query(vector, top_k=5)
    emit(
        {
            "type": "step",
            "stage": "retrieve",
            "title": f"Vector retrieval \u2014 {len(candidates)} candidate(s)",
            "items": [
                {
                    "node_id": node.node_id,
                    "entity": node.entity,
                    "content": _short(node.content),
                    "similarity": round(float(sim), 3),
                }
                for node, sim in candidates
            ],
        }
    )

    # 3) Re-verify every candidate's Ed25519 signature + content hash.
    verified_rows = []
    scored = []
    for node, sim in candidates:
        ok = mem.verify(node)
        confidence = round(max(float(sim), 0.0), 3) if ok else 0.0
        verified_rows.append(
            {
                "node_id": node.node_id,
                "verified": ok,
                "hash": node.crypto.hash[:12] + ".." if node.crypto else None,
            }
        )
        if ok:
            scored.append((node, confidence))
    emit(
        {
            "type": "step",
            "stage": "verify",
            "title": "Signature verification (SHA-256 + Ed25519)",
            "detail": "Tampered or unsigned nodes are dropped before they can ground an answer.",
            "items": verified_rows,
        }
    )

    # 4) Grounding gate: only verified facts above the relevance threshold pass.
    admitted = [(n, c) for n, c in scored if c >= MIN_CONFIDENCE]
    admitted.sort(key=lambda pair: pair[1], reverse=True)
    grounded = bool(admitted)
    emit(
        {
            "type": "step",
            "stage": "gate",
            "title": "Grounding gate",
            "detail": f"threshold = {MIN_CONFIDENCE:.2f} \u00b7 "
            + ("PASS \u2014 grounding" if grounded else "EMPTY \u2014 must abstain"),
            "decision": "grounded" if grounded else "abstain",
            "items": [
                {"node_id": n.node_id, "entity": n.entity, "confidence": c} for n, c in admitted
            ],
        }
    )

    if not grounded:
        provenance = {
            "grounded": False,
            "injected_nodes": [],
            "ledger_root": mem.ledger_root(),
            "verified": False,
        }
        return "NO_VERIFIED_MEMORY: abstain; do not guess.", provenance

    # 5) Provenance: ledger root + the exact signed nodes that will ground the answer.
    provenance = {
        "grounded": True,
        "injected_nodes": [n.node_id for n, _ in admitted],
        "ledger_root": mem.ledger_root(),
        "verified": True,
        "facts": [{"node_id": n.node_id, "entity": n.entity, "confidence": c} for n, c in admitted],
    }
    emit(
        {
            "type": "step",
            "stage": "generate",
            "title": "Synthesize grounded answer",
            "detail": "Local model is composing an answer from the verified facts only\u2026",
        }
    )

    facts_block = "VERIFIED_FACTS:\n" + "\n".join(
        f"- [{n.node_id}] ({n.entity}) {n.content} (confidence={c:.2f})" for n, c in admitted
    )
    return facts_block, provenance


def build_agent(tool: Callable[..., str], model_id: str | None = None, host: str | None = None):
    """Build the agno agent wired to a single verified-memory ``tool``."""
    from agno.agent import Agent
    from agno.models.ollama import Ollama

    return Agent(
        name="Verified Memory Agent",
        model=Ollama(
            id=model_id or MODEL_ID,
            host=host or OLLAMA_HOST,
            options={"num_ctx": NUM_CTX},
        ),
        tools=[tool],
        instructions=(
            "You answer strictly from cryptographically verified memory.\n"
            "1. ALWAYS call recall_verified_memory before answering a factual question.\n"
            "2. Answer ONLY using the VERIFIED_FACTS returned, and cite the node ids in "
            "square brackets, e.g. [mem_ab12cd34].\n"
            "3. If recall_verified_memory returns NO_VERIFIED_MEMORY, reply that you cannot "
            "answer that from verified memory. Never guess."
        ),
        markdown=True,
    )
