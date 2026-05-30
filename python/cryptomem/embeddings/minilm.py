from __future__ import annotations

from functools import lru_cache
from typing import Any

from cryptomem.embeddings.base import Embedder

_DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=4)
def _load_model(name: str) -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - exercised only without extra
        raise ImportError(
            "MiniLMEmbedder requires the 'local' extra: pip install 'cryptomem[local]'"
        ) from exc
    return SentenceTransformer(name)


class MiniLMEmbedder(Embedder):
    """CPU-friendly semantic embedder backed by ``all-MiniLM-L6-v2`` (~80 MB).

    The model is loaded lazily on first ``embed`` call so importing the package
    stays cheap and model-free. Install with the ``local`` extra.
    """

    def __init__(self, model_name: str = _DEFAULT_MODEL, dim: int = 384):
        self.model_name = model_name
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        model = _load_model(self.model_name)
        vector = model.encode(text, normalize_embeddings=True)
        return [float(x) for x in vector]
