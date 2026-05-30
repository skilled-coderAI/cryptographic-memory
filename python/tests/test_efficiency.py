from __future__ import annotations

from cryptomem.efficiency import (
    SemanticCache,
    compress_heuristic,
    count_tokens,
    dedupe,
    fit_to_budget,
)
from cryptomem.efficiency.budgeter import count_tokens as ct
from cryptomem.embeddings.stub import StubEmbedder
from cryptomem.models import MemoryNode, ScoredNode

_EMB = StubEmbedder()


def _scored(node_id: str, content: str, score: float = 1.0) -> ScoredNode:
    node = MemoryNode(node_id=node_id, entity="E", content=content, embedding=_EMB.embed(content))
    return ScoredNode(node=node, score=score, verified=True, confidence=score)


def test_count_tokens_positive():
    assert count_tokens("hello world from cryptomem") > 0


def test_fit_to_budget_never_exceeds():
    nodes = [_scored(f"n{i}", f"fact number {i} with some words") for i in range(5)]
    budget = ct(nodes[0].node.content) + ct(nodes[1].node.content)
    kept = fit_to_budget(nodes, budget)
    total = sum(ct(s.node.content) for s in kept)
    assert total <= budget
    assert len(kept) >= 1


def test_dedupe_removes_near_duplicates():
    nodes = [
        _scored("n1", "the budget was approved at four million"),
        _scored("n2", "the budget was approved at four million"),
        _scored("n3", "the launch venue is the rooftop"),
    ]
    kept = dedupe(nodes, threshold=0.95)
    ids = {s.node.node_id for s in kept}
    assert "n1" in ids
    assert "n2" not in ids
    assert "n3" in ids


def test_compress_heuristic_drops_filler_keeps_facts():
    out = compress_heuristic("The budget of the project was approved at $4.2M")
    assert "$4.2M" in out
    assert "the" not in out.lower().split()


def test_semantic_cache_hit_and_miss():
    cache = SemanticCache(threshold=0.97)
    key = _EMB.embed("what is the phoenix budget")
    assert cache.get(key) is None
    cache.put(key, "4.2M")
    assert cache.get(_EMB.embed("what is the phoenix budget")) == "4.2M"
    assert cache.get(_EMB.embed("totally unrelated weather question")) is None
