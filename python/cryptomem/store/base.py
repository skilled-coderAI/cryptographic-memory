from __future__ import annotations

from abc import ABC, abstractmethod

from cryptomem.models import MemoryNode


class MemoryStore(ABC):
    """Persistence + retrieval contract shared by every backend."""

    @abstractmethod
    def write(self, node: MemoryNode) -> None:
        """Insert or replace a node by ``node_id``."""

    @abstractmethod
    def get(self, node_id: str) -> MemoryNode | None:
        """Fetch a single node, or ``None`` if it does not exist."""

    @abstractmethod
    def query(self, embedding: list[float], top_k: int = 5) -> list[tuple[MemoryNode, float]]:
        """Return up to ``top_k`` nodes ranked by similarity to ``embedding``."""

    @abstractmethod
    def neighbors(self, node_id: str, depth: int = 1) -> list[MemoryNode]:
        """Traverse outgoing relationships up to ``depth`` hops."""

    @abstractmethod
    def all(self) -> list[MemoryNode]:
        """Return every stored node."""
