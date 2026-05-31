from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cryptomem.client import MemoryClient


class TriggerEngine:
    """Rule-based proactive triggers over the current verified memory.

    Surfaces actionable suggestions without being asked: reconciliation for
    contradictory facts, refresh for expired (TTL) facts, and link-gap hints
    for isolated nodes. Hybrid embedding rules can be layered on later; these
    deterministic rules already cover the architecture's headline cases.
    """

    def __init__(self, client: MemoryClient):
        self.client = client

    def evaluate(self) -> list[dict]:
        """Return a list of ``{type, ...}`` suggestion dicts."""
        out: list[dict] = []
        for c in self.client.contradictions():
            out.append(
                {
                    "type": "reconcile",
                    "entity": c.entity,
                    "node_ids": [c.left_id, c.right_id],
                    "reason": "divergent facts for the same entity",
                }
            )
        now = datetime.now(timezone.utc)
        for node in self.client.store.all():
            if not self.client.verify(node):
                continue
            expires_at = node.metadata.get("expires_at")
            if isinstance(expires_at, str):
                try:
                    if datetime.fromisoformat(expires_at) < now:
                        out.append(
                            {
                                "type": "refresh",
                                "node_id": node.node_id,
                                "reason": "fact ttl expired",
                            }
                        )
                except ValueError:
                    pass
            if not node.relationships:
                out.append(
                    {
                        "type": "link_gap",
                        "node_id": node.node_id,
                        "reason": "no relationships recorded",
                    }
                )
        return out
