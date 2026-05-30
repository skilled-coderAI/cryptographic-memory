from __future__ import annotations

import math
from abc import ABC, abstractmethod


class Embedder(ABC):
    """Maps text to a fixed-dimension vector for semantic retrieval."""

    dim: int

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for ``text``."""


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in ``[-1, 1]``; ``0.0`` if either vector is empty/zero."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
