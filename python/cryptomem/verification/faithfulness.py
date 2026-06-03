from __future__ import annotations

import re

from cryptomem.embeddings.base import Embedder, cosine_similarity
from cryptomem.models import ScoredNode

_BOUNDARY = re.compile(r"(?:(?<!\d)[.!?]|[.!?](?!\d))+")


def split_sentences(text: str) -> list[str]:
    """Split text into trimmed, non-empty sentences (model-free).

    A ``.`` flanked by digits (e.g. ``$4.2M``) is treated as a decimal point,
    not a sentence boundary, so numeric claims stay intact.
    """
    return [s.strip() for s in _BOUNDARY.split(text) if s.strip()]


class FaithfulnessChecker:
    """Scores how well an answer is supported by the injected verified facts.

    Model-free by default: each answer sentence is scored by its maximum cosine
    similarity to any injected fact, and the answer score is the mean over
    sentences. This is a hallucination guard, not a paraphrase detector; an
    unsupported sentence drags the score down so the caller can flag or reject
    the answer.
    """

    def __init__(self, embedder: Embedder, threshold: float = 0.25):
        self.embedder = embedder
        self.threshold = threshold

    def score(self, answer: str, facts: list[ScoredNode]) -> tuple[float, list[float]]:
        """Return ``(overall, per_sentence)`` support scores in ``[0, 1]``."""
        sentences = split_sentences(answer)
        if not sentences or not facts:
            return 0.0, []
        fact_vecs = [f.node.embedding or self.embedder.embed(f.node.content) for f in facts]
        per_sentence: list[float] = []
        for sent in sentences:
            sv = self.embedder.embed(sent)
            best = max((cosine_similarity(sv, fv) for fv in fact_vecs), default=0.0)
            per_sentence.append(round(max(best, 0.0), 4))
        overall = round(sum(per_sentence) / len(per_sentence), 4)
        return overall, per_sentence

    def is_faithful(self, answer: str, facts: list[ScoredNode]) -> bool:
        """``True`` when overall support meets ``threshold``."""
        overall, _ = self.score(answer, facts)
        return overall >= self.threshold
