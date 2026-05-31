from __future__ import annotations

from collections.abc import Callable

from cryptomem.models import MemoryNode
from cryptomem.store.base import MemoryStore


class Planner:
    """Anticipates the next-needed facts by walking the knowledge graph.

    Given the verified nodes that were just injected, it pre-stages adjacent,
    not-yet-used nodes as suggestions for the likely follow-up question. Only
    verified neighbours are surfaced, so proactivity never leaks unverified
    content.
    """

    def __init__(self, store: MemoryStore, verify: Callable[[MemoryNode], bool]):
        self.store = store
        self.verify = verify

    def suggest(self, injected: list[MemoryNode], limit: int = 3) -> list[dict]:
        """Return up to ``limit`` ``{type, node_id, reason}`` suggestions."""
        injected_ids = {n.node_id for n in injected}
        seen: set[str] = set()
        suggestions: list[dict] = []
        for node in injected:
            for rel in node.relationships:
                target_id = rel.target_id
                if target_id in injected_ids or target_id in seen:
                    continue
                target = self.store.get(target_id)
                if target is None or not self.verify(target):
                    continue
                seen.add(target_id)
                suggestions.append(
                    {
                        "type": "related_fact",
                        "node_id": target_id,
                        "reason": f"{rel.type} {node.entity}",
                    }
                )
                if len(suggestions) >= limit:
                    return suggestions
        return suggestions
