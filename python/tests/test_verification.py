from __future__ import annotations

from cryptomem import MemoryClient, Settings
from cryptomem.crypto.signer import Signer
from cryptomem.store.sqlite_store import SqliteStore
from cryptomem.verification import Citer, FaithfulnessChecker, SemanticEntropy


def test_faithfulness_supported_scores_higher(client: MemoryClient):
    client.archive("Project Phoenix", "Budget approved at 4.2M for FY26.")
    facts = client.query("phoenix budget", top_k=3)
    checker = FaithfulnessChecker(client.embedder)
    supported, _ = checker.score("Budget approved at 4.2M for FY26.", facts)
    unsupported, _ = checker.score("The weather on Mars is freezing today.", facts)
    assert supported > unsupported
    assert checker.is_faithful("Budget approved at 4.2M for FY26.", facts)


def test_citations_attach_supporting_node_id(client: MemoryClient):
    node = client.archive("Project Phoenix", "Budget approved at 4.2M for FY26.")
    facts = client.query("phoenix budget", top_k=3)
    annotated, citations = Citer(client.embedder).annotate(
        "Budget approved at 4.2M for FY26.", facts
    )
    assert node.node_id in annotated
    assert citations[0]["node_id"] == node.node_id


def test_semantic_entropy_agreement_vs_scatter(client: MemoryClient):
    se = SemanticEntropy(client.embedder)
    agree = se.score(["the cat sat", "the cat sat", "the cat sat"])
    assert agree["clusters"] == 1
    assert agree["confidence"] == 1.0
    scatter = se.score(
        ["the cat sat on the mat", "stock prices fell sharply", "purple monkey dishwasher"]
    )
    assert scatter["clusters"] >= 2
    assert scatter["confidence"] < 1.0


def test_confidence_abstains_without_memory(client: MemoryClient):
    result = client.confidence("a topic with no stored facts")
    assert result["confidence"] == 0.0


def test_confidence_high_with_deterministic_adapter(client: MemoryClient):
    client.archive("Project Phoenix", "Budget approved at 4.2M for FY26.")
    result = client.confidence("phoenix budget", samples=3)
    assert result["clusters"] == 1
    assert result["confidence"] == 1.0


def test_cove_verifies_and_flags(client: MemoryClient):
    client.archive("Project Phoenix", "Budget approved at 4.2M for FY26.")
    good = client.verify_answer("Budget approved at 4.2M for FY26.")
    assert good["verdict"] == "verified"
    assert good["supported_ratio"] == 1.0
    bad = client.verify_answer("Mars has two moons named Phobos and Deimos.")
    assert bad["verdict"] == "unverified"


def test_respond_emits_citations_and_faithfulness_when_enabled():
    settings = Settings(sqlite_path=":memory:", enable_citations=True, enable_faithfulness=True)
    client = MemoryClient(
        settings=settings, store=SqliteStore(":memory:"), signer=Signer.generate()
    )
    client.archive("Project Phoenix", "Budget approved at 4.2M for FY26.")
    _, provenance = client.respond("phoenix budget")
    assert "citations" in provenance
    assert "faithfulness" in provenance
    assert "faithful" in provenance
