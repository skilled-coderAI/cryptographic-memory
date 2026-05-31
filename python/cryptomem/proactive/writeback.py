from __future__ import annotations

from typing import TYPE_CHECKING

from cryptomem.models import MemoryNode
from cryptomem.proactive.extractor import extract_facts
from cryptomem.retrieval.retriever import extract_entities

if TYPE_CHECKING:
    from cryptomem.client import MemoryClient


class WriteBack:
    """Self-growing memory: stage asserted facts as signed ``pending`` nodes.

    Facts parsed from a model response are signed and persisted with
    ``status="pending"`` so memory grows automatically while keeping a
    human-in-the-loop confirmation step before they count as trusted.
    """

    def __init__(self, client: MemoryClient):
        self.client = client

    def stage(self, text: str, entity: str | None = None) -> list[MemoryNode]:
        """Extract facts from ``text`` and persist each as a pending node."""
        staged: list[MemoryNode] = []
        for fact in extract_facts(text):
            resolved = entity or next(iter(extract_entities(fact)), "conversation")
            node = self.client.archive(
                entity=resolved,
                content=fact,
                metadata={"status": "pending", "source": "writeback"},
            )
            staged.append(node)
        return staged
