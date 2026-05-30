from __future__ import annotations

from cryptomem.embeddings.base import cosine_similarity


class SemanticCache:
    """Caches answers keyed by query embedding; hits skip the model entirely.

    A lookup returns a stored answer when an existing key's cosine similarity
    meets ``threshold``. Bounded by ``max_entries`` (FIFO eviction).
    """

    def __init__(self, threshold: float = 0.97, max_entries: int = 256):
        self.threshold = threshold
        self.max_entries = max_entries
        self._entries: list[tuple[list[float], str]] = []

    def get(self, query_embedding: list[float]) -> str | None:
        best: tuple[float, str] | None = None
        for emb, answer in self._entries:
            sim = cosine_similarity(query_embedding, emb)
            if sim >= self.threshold and (best is None or sim > best[0]):
                best = (sim, answer)
        return best[1] if best else None

    def put(self, query_embedding: list[float], answer: str) -> None:
        self._entries.append((query_embedding, answer))
        if len(self._entries) > self.max_entries:
            self._entries.pop(0)

    def __len__(self) -> int:
        return len(self._entries)
