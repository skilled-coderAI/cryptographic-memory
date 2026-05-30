from __future__ import annotations

import hashlib
import math
import re

from cryptomem.embeddings.base import Embedder

_TOKEN = re.compile(r"[a-z0-9]+")


class StubEmbedder(Embedder):
    """Deterministic, model-free hashing embedder.

    Produces a normalized bag-of-words vector so retrieval works out of the box
    on CPU-only hardware with zero model downloads. Swap in ``MiniLMEmbedder``
    (the ``local`` extra) for semantic quality.
    """

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN.findall(text.lower()):
            bucket = int(hashlib.sha256(token.encode()).hexdigest(), 16) % self.dim
            vec[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return vec
        return [v / norm for v in vec]
