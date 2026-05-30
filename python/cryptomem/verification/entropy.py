from __future__ import annotations

import math

from cryptomem.adapters.base import LLMAdapter
from cryptomem.embeddings.base import Embedder, cosine_similarity


class SemanticEntropy:
    """Embedding-based semantic entropy as an epistemic confidence signal.

    Multiple sampled answers are clustered by meaning (cosine >= threshold).
    Agreement across samples collapses into one cluster (low entropy, high
    confidence); scattered, contradictory samples spread across clusters (high
    entropy, low confidence). Model-free aside from the embedder + adapter.
    """

    def __init__(
        self,
        embedder: Embedder,
        cluster_threshold: float = 0.8,
    ):
        self.embedder = embedder
        self.cluster_threshold = cluster_threshold

    def cluster(self, answers: list[str]) -> list[list[int]]:
        """Greedily group answer indices into meaning clusters."""
        vecs = [self.embedder.embed(a) for a in answers]
        clusters: list[list[int]] = []
        centroids: list[list[float]] = []
        for idx, vec in enumerate(vecs):
            placed = False
            for c_idx, centroid in enumerate(centroids):
                if cosine_similarity(vec, centroid) >= self.cluster_threshold:
                    clusters[c_idx].append(idx)
                    placed = True
                    break
            if not placed:
                clusters.append([idx])
                centroids.append(vec)
        return clusters

    def score(self, answers: list[str]) -> dict:
        """Return ``{clusters, entropy, confidence}`` for sampled answers."""
        answers = [a for a in answers if a.strip()]
        if not answers:
            return {"clusters": 0, "entropy": 1.0, "confidence": 0.0}
        clusters = self.cluster(answers)
        total = len(answers)
        entropy = 0.0
        for members in clusters:
            p = len(members) / total
            entropy -= p * math.log(p)
        max_entropy = math.log(total) if total > 1 else 1.0
        normalized = entropy / max_entropy if max_entropy > 0 else 0.0
        return {
            "clusters": len(clusters),
            "entropy": round(normalized, 4),
            "confidence": round(1.0 - normalized, 4),
        }

    def estimate(self, prompt: str, adapter: LLMAdapter, samples: int = 5) -> dict:
        """Sample ``adapter`` ``samples`` times and score semantic agreement."""
        answers = [adapter.complete(prompt) for _ in range(max(samples, 1))]
        return self.score(answers)
