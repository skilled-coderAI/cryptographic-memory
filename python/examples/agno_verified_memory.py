"""Verified memory for an agno agent.

Gives an `agno <https://github.com/agno-agi/agno>`_ agent cryptographically
verified, relational memory via three tools backed by an in-process
``cryptomem.MemoryClient``. The agent answers ONLY from signature-verified
facts, or abstains -- watch it ground one question and refuse another.

Run it::

    ollama pull qwen2.5:0.5b && ollama serve
    pip install "cryptomem[local,agno]"   # published on PyPI
    python python/examples/agno_verified_memory.py

The MemoryClient honours ``CRYPTOMEM_*`` env vars, so the same agent works
against the default local SQLite store, a Neo4j graph, or a remote ledger
backend by changing only ``CRYPTOMEM_MODE`` / ``CRYPTOMEM_BACKEND_URL``.
"""

from __future__ import annotations

import json
import os
import textwrap

from cryptomem import MemoryClient, Relationship

MEM = MemoryClient()

RECALL_MIN_CONFIDENCE = float(os.environ.get("CRYPTOMEM_RECALL_MIN_CONFIDENCE", "0.35"))


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

    Only signature-verified memory nodes that are also relevant enough to the
    query (confidence >= RECALL_MIN_CONFIDENCE) are returned. If nothing
    verified and relevant matches, an explicit NO_VERIFIED_MEMORY notice is
    returned and you MUST abstain instead of guessing. Ground every answer in
    these facts and cite the node ids in square brackets.
    """
    verified = [
        h
        for h in MEM.query(query, top_k=5)
        if h.verified and h.confidence >= RECALL_MIN_CONFIDENCE
    ]
    if not verified:
        return "NO_VERIFIED_MEMORY: abstain; do not guess."
    return "VERIFIED_FACTS:\n" + "\n".join(
        f"- [{h.node.node_id}] ({h.node.entity}) {h.node.content} "
        f"(confidence={h.confidence:.2f})"
        for h in verified
    )


def archive_fact(entity: str, content: str, source: str = "agno-agent") -> str:
    """Persist a new fact as a signed, verifiable memory node.

    Returns the new node id and its verification status.
    """
    node = MEM.archive(entity, content, metadata={"source": source})
    return f"archived node_id={node.node_id} verified={MEM.verify(node)}"


def verify_claim(claim: str) -> str:
    """Re-check a drafted claim against verified memory (Chain-of-Verification).

    Use before asserting a fact. Returns a JSON verdict per extracted claim.
    """
    return json.dumps(MEM.verify_answer(claim))


def build_agent():
    """Build an agno agent wired to the verified-memory tools."""
    from agno.agent import Agent
    from agno.models.ollama import Ollama

    host = os.environ.get("CRYPTOMEM_OLLAMA_URL", "http://localhost:11434")
    model_id = os.environ.get("AGNO_MODEL", "qwen2.5:0.5b")
    return Agent(
        name="Verified Memory Agent",
        model=Ollama(id=model_id, host=host),
        tools=[recall_verified_memory, archive_fact, verify_claim],
        instructions=textwrap.dedent(
            """
            You answer strictly from cryptographically verified memory.
            1. ALWAYS call recall_verified_memory before answering a factual question.
            2. Answer ONLY using the VERIFIED_FACTS returned, and cite the node ids
               in square brackets.
            3. If recall_verified_memory returns NO_VERIFIED_MEMORY, reply that you
               cannot answer that from verified memory. Never guess.
            4. Use archive_fact to store durable new facts; verify_claim to re-check
               a draft before asserting it.
            """
        ).strip(),
        markdown=True,
    )


def main() -> None:
    _seed()
    try:
        agent = build_agent()
    except ModuleNotFoundError:
        print('agno is not installed. Run: pip install "cryptomem[agno]"')
        print("and start a local model with: ollama serve")
        raise

    # Grounded: answerable from a verified, signed fact.
    agent.print_response("What budget did Project Phoenix get, and who approved it?")

    # Abstains: nothing verified covers this.
    agent.print_response("What is the launch date of Project Hydra?")


if __name__ == "__main__":
    main()
