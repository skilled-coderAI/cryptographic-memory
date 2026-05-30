from __future__ import annotations

import re
from collections.abc import Callable

from cryptomem.embeddings.base import Embedder, cosine_similarity
from cryptomem.models import MemoryNode, ScoredNode
from cryptomem.store.base import MemoryStore

_ENTITY = re.compile(r"\b[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*")


def extract_entities(text: str) -> list[str]:
    """Cheap, model-free proper-noun extraction for intent/graph hints."""
    seen: dict[str, None] = {}
    for match in _ENTITY.findall(text):
        seen.setdefault(match, None)
    return list(seen)


class Retriever:
    """Vector search + graph expansion + verification + ranking.

    Candidates come from a vector query, optionally expanded one or more hops
    along the knowledge graph. Every node is verified; unverified nodes are
    dropped when ``require_verification`` is set. Results are ranked by
    similarity discounted by graph distance.
    """

    def __init__(
        self,
        store: MemoryStore,
        embedder: Embedder,
        verify: Callable[[MemoryNode], bool],
        require_verification: bool = True,
        edge_penalty: float = 0.1,
    ):
        self.store = store
        self.embedder = embedder
        self.verify = verify
        self.require_verification = require_verification
        self.edge_penalty = edge_penalty

    def retrieve(self, text: str, top_k: int = 5, depth: int = 0) -> list[ScoredNode]:
        query_vec = self.embedder.embed(text)
        distance: dict[str, int] = {}
        candidates: dict[str, MemoryNode] = {}

        for node, _score in self.store.query(query_vec, top_k=top_k):
            candidates[node.node_id] = node
            distance[node.node_id] = 0

        if depth > 0:
            for seed_id in list(candidates):
                for hop, neighbour in enumerate(
                    self.store.neighbors(seed_id, depth=depth), start=1
                ):
                    if neighbour.node_id not in candidates:
                        candidates[neighbour.node_id] = neighbour
                        distance[neighbour.node_id] = hop

        scored: list[ScoredNode] = []
        for node_id, node in candidates.items():
            verified = self.verify(node)
            if self.require_verification and not verified:
                continue
            sim = cosine_similarity(query_vec, node.embedding) if node.embedding else 0.0
            adjusted = sim - self.edge_penalty * distance[node_id]
            confidence = round(max(adjusted, 0.0), 4) if verified else 0.0
            scored.append(
                ScoredNode(
                    node=node,
                    score=round(adjusted, 4),
                    verified=verified,
                    confidence=confidence,
                )
            )

        scored.sort(key=lambda s: s.score, reverse=True)
        return scored
