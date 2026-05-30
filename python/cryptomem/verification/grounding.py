from __future__ import annotations

from cryptomem.models import ScoredNode


def render_context(nodes: list[ScoredNode]) -> str:
    """Render verified nodes as compact, citable ``entity: content`` lines."""
    return "\n".join(
        f"- {s.node.entity}: {s.node.content} (node {s.node.node_id}, confidence {s.confidence})"
        for s in nodes
    )


class GroundingGate:
    """Strict gate that admits only verified, sufficiently confident facts.

    Returns the admissible nodes plus a boolean: when nothing passes, the
    caller must abstain rather than answer from unverified context.
    """

    def __init__(self, min_confidence: float = 0.0):
        self.min_confidence = min_confidence

    def admit(self, scored: list[ScoredNode]) -> tuple[list[ScoredNode], bool]:
        admitted = [s for s in scored if s.verified and s.confidence >= self.min_confidence]
        return admitted, bool(admitted)
