"""Simple agno agent grounded in cryptomem verified memory (local Ollama).

A minimal, copy-pasteable starting point: one local model, one verified-memory
tool, two questions -- one the agent can answer from a signed fact, and one it
must refuse. Built for a tiny local model such as ``qwen3.5:0.8b`` served by
Ollama on your own machine.

Run it::

    ollama serve                       # qwen3.5:0.8b already pulled locally
    pip install "cryptomem[local,agno]" ollama
    python examples/agno_quickstart.py

Configuration (all optional, sensible defaults):

    AGNO_MODEL            Ollama model id          (default: qwen3.5:0.8b)
    CRYPTOMEM_OLLAMA_URL  Ollama base URL          (default: http://localhost:11434)
    CRYPTOMEM_MODE        sqlite | neo4j | remote  (memory backend; default sqlite)
    CRYPTOMEM_BACKEND_URL remote ledger backend URL when CRYPTOMEM_MODE=remote
    CRYPTOMEM_SQLITE_PATH file path to persist memory across runs (default :memory:)
    MEM_MIN_CONFIDENCE    relevance gate for grounding (default: 0.30)

The memory backend is chosen entirely from ``CRYPTOMEM_*`` env vars, so the same
agent runs against a local SQLite store, a Neo4j graph, or a remote ledger
backend URL with no code changes.
"""

from __future__ import annotations

import os
import textwrap

from cryptomem import MemoryClient, Relationship

# --- relevance gate: how similar a verified fact must be to count as grounding.
MIN_CONFIDENCE = float(os.environ.get("MEM_MIN_CONFIDENCE", "0.30"))


def _build_embedder():
    """Prefer real semantic embeddings (MiniLM); fall back to the stub.

    MiniLM gives meaningful similarity scores so the agent grounds on relevant
    facts and abstains on the rest. If the ``local`` extra (or the model
    download) is unavailable, we degrade to the model-free stub embedder.
    """
    try:
        from cryptomem import MiniLMEmbedder

        embedder = MiniLMEmbedder()
        embedder.embed("warmup")  # surface download/offline errors now, not mid-run
        print("[memory] embedder: MiniLM (semantic)")
        return embedder
    except Exception as exc:  # noqa: BLE001 - intentional graceful fallback
        from cryptomem import StubEmbedder

        print(f"[memory] embedder: stub (MiniLM unavailable: {exc})")
        return StubEmbedder()


MEM = MemoryClient(embedder=_build_embedder())


def _seed() -> None:
    """Seed a couple of signed, related facts (idempotent)."""
    if any(h.verified for h in MEM.query("Project Phoenix budget", top_k=1)):
        return
    owner = MEM.archive("Alice Chen", "Alice Chen is the finance lead for FY26.")
    MEM.archive(
        "Project Phoenix",
        "Project Phoenix budget was approved at $4.2M for FY26.",
        relationships=[Relationship(type="approved_by", target_id=owner.node_id)],
        metadata={"source": "Q3-board-minutes.pdf"},
    )


def recall_verified_memory(query: str) -> str:
    """Retrieve cryptographically verified facts relevant to `query`.

    Only signature-verified memory nodes that clear the relevance gate are
    returned. If nothing verified is relevant, an explicit NO_VERIFIED_MEMORY
    notice is returned and you MUST abstain instead of guessing. Ground every
    answer in these facts and cite the node ids in square brackets.
    """
    hits = [h for h in MEM.query(query, top_k=5) if h.verified and h.confidence >= MIN_CONFIDENCE]
    if not hits:
        return "NO_VERIFIED_MEMORY: abstain; do not guess."
    return "VERIFIED_FACTS:\n" + "\n".join(
        f"- [{h.node.node_id}] ({h.node.entity}) {h.node.content} (confidence={h.confidence:.2f})"
        for h in hits
    )


def build_agent():
    """Build a minimal agno agent wired to the verified-memory tool."""
    from agno.agent import Agent
    from agno.models.ollama import Ollama

    host = os.environ.get("CRYPTOMEM_OLLAMA_URL", "http://localhost:11434")
    model_id = os.environ.get("AGNO_MODEL", "qwen3.5:0.8b")
    print(f"[agent] model={model_id} host={host}")

    return Agent(
        name="Verified Memory Agent",
        model=Ollama(id=model_id, host=host),
        tools=[recall_verified_memory],
        instructions=textwrap.dedent(
            """
            You answer strictly from cryptographically verified memory.
            1. ALWAYS call recall_verified_memory before answering a factual question.
            2. Answer ONLY using the VERIFIED_FACTS returned, and cite the node ids
               in square brackets, e.g. [mem_ab12cd34].
            3. If recall_verified_memory returns NO_VERIFIED_MEMORY, reply that you
               cannot answer that from verified memory. Never guess.
            """
        ).strip(),
        markdown=True,
    )


def main() -> None:
    _seed()
    try:
        agent = build_agent()
    except ModuleNotFoundError:
        print('agno/ollama not installed. Run: pip install "cryptomem[agno]" ollama')
        raise

    # Grounded: answerable from a verified, signed fact.
    agent.print_response("What budget did Project Phoenix get, and who approved it?")

    # Abstains: nothing verified covers this.
    agent.print_response("What is the launch date of Project Hydra?")


if __name__ == "__main__":
    main()
