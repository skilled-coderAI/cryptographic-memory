from __future__ import annotations

from typing import TYPE_CHECKING

from cryptomem.embeddings.base import Embedder
from cryptomem.verification.faithfulness import FaithfulnessChecker, split_sentences

if TYPE_CHECKING:
    from cryptomem.client import MemoryClient


class ChainOfVerification:
    """Chain-of-Verification: re-checks each draft claim against memory.

    The draft answer is decomposed into atomic claims; each claim is treated as
    a verification question, re-retrieved from verified memory, and scored for
    support. Unsupported claims are flagged so the caller can revise or abstain.
    Model-free orchestration over an existing :class:`MemoryClient`.
    """

    def __init__(self, client: MemoryClient, embedder: Embedder, threshold: float = 0.25):
        self.client = client
        self.checker = FaithfulnessChecker(embedder, threshold=threshold)
        self.threshold = threshold

    def verify(self, draft: str, top_k: int = 3) -> dict:
        """Return per-claim support plus an overall verdict for ``draft``."""
        claims = split_sentences(draft)
        checks: list[dict] = []
        supported = 0
        for claim in claims:
            facts = self.client.query(claim, top_k=top_k)
            score, _ = self.checker.score(claim, facts)
            ok = bool(facts) and score >= self.threshold
            supported += int(ok)
            checks.append(
                {
                    "claim": claim,
                    "support": score,
                    "supported": ok,
                    "evidence": [f.node.node_id for f in facts],
                }
            )
        ratio = round(supported / len(claims), 4) if claims else 0.0
        return {
            "claims": len(claims),
            "supported": supported,
            "supported_ratio": ratio,
            "verdict": "verified" if claims and supported == len(claims) else "unverified",
            "checks": checks,
        }
