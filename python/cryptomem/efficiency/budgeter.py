from __future__ import annotations

from functools import lru_cache
from typing import Any

from cryptomem.models import ScoredNode


@lru_cache(maxsize=1)
def _encoder() -> Any | None:
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # pragma: no cover - offline / extra-not-installed fallback
        return None


def count_tokens(text: str) -> int:
    """Token count via ``tiktoken`` when available, else a word-count fallback."""
    enc = _encoder()
    if enc is None:
        return len(text.split())
    return len(enc.encode(text))


def fit_to_budget(nodes: list[ScoredNode], max_tokens: int) -> list[ScoredNode]:
    """Greedily keep the highest-ranked nodes whose total stays within budget.

    Assumes ``nodes`` is pre-ranked. Never exceeds ``max_tokens``.
    """
    out: list[ScoredNode] = []
    used = 0
    for node in nodes:
        cost = count_tokens(node.node.content)
        if used + cost > max_tokens:
            continue
        out.append(node)
        used += cost
    return out
