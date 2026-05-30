from __future__ import annotations

from cryptomem.embeddings.base import cosine_similarity
from cryptomem.models import ScoredNode


def dedupe(nodes: list[ScoredNode], threshold: float = 0.95) -> list[ScoredNode]:
    """Suppress near-duplicate nodes by embedding cosine similarity.

    Iterates in the given (pre-ranked) order, keeping a node only if it is not
    too similar to one already kept.
    """
    kept: list[ScoredNode] = []
    for candidate in nodes:
        emb = candidate.node.embedding
        if emb is None:
            kept.append(candidate)
            continue
        if any(
            k.node.embedding is not None and cosine_similarity(emb, k.node.embedding) >= threshold
            for k in kept
        ):
            continue
        kept.append(candidate)
    return kept
