from __future__ import annotations

from cryptomem.embeddings.base import Embedder, cosine_similarity
from cryptomem.models import ScoredNode
from cryptomem.verification.faithfulness import split_sentences


class Citer:
    """Maps each answer sentence to its best-supporting verified node.

    Model-free: similarity is computed against fact embeddings. Sentences whose
    best support clears ``min_support`` get an inline ``[node_id]`` citation;
    those below are reported as uncited so the caller can surface or reject
    unverifiable claims.
    """

    def __init__(self, embedder: Embedder, min_support: float = 0.2):
        self.embedder = embedder
        self.min_support = min_support

    def annotate(self, answer: str, facts: list[ScoredNode]) -> tuple[str, list[dict]]:
        """Return ``(annotated_answer, citations)``.

        Each citation is ``{sentence, node_id, support}``; ``node_id`` is
        ``None`` for sentences with no fact above ``min_support``.
        """
        sentences = split_sentences(answer)
        if not sentences or not facts:
            return answer, []
        fact_vecs = [
            (f.node.node_id, f.node.embedding or self.embedder.embed(f.node.content)) for f in facts
        ]
        cited_parts: list[str] = []
        citations: list[dict] = []
        for sent in sentences:
            sv = self.embedder.embed(sent)
            best_id: str | None = None
            best_sim = 0.0
            for node_id, fv in fact_vecs:
                sim = cosine_similarity(sv, fv)
                if sim > best_sim:
                    best_sim, best_id = sim, node_id
            if best_id is not None and best_sim >= self.min_support:
                cited_parts.append(f"{sent} [{best_id}]")
                citations.append(
                    {"sentence": sent, "node_id": best_id, "support": round(best_sim, 4)}
                )
            else:
                cited_parts.append(sent)
                citations.append({"sentence": sent, "node_id": None, "support": round(best_sim, 4)})
        return " ".join(cited_parts), citations
