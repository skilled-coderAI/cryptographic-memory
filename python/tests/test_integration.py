from __future__ import annotations

from cryptomem import ABSTAIN, MemoryClient
from cryptomem.models import Relationship


def test_archive_then_query_returns_verified(client: MemoryClient):
    client.archive("Project Phoenix", "Budget approved at $4.2M for FY26.")
    hits = client.query("What budget did Project Phoenix get?")
    assert hits, "expected at least one verified hit"
    assert hits[0].verified is True
    assert hits[0].confidence > 0.0


def test_answer_grounds_on_verified_fact(client: MemoryClient):
    client.archive("Project Phoenix", "Budget approved at $4.2M for FY26.")
    answer = client.answer("What budget did Project Phoenix get?")
    assert answer != ABSTAIN
    assert "4.2M" in answer


def test_answer_abstains_when_empty(client: MemoryClient):
    assert client.answer("Anything at all?") == ABSTAIN


def test_poisoned_node_is_rejected_and_answer_abstains(client: MemoryClient):
    node = client.archive("Project Phoenix", "Budget approved at $4.2M for FY26.")

    poisoned = client.store.get(node.node_id)
    assert poisoned is not None
    poisoned.content = "Budget approved at $9.9M for FY26."
    client.store.write(poisoned)

    assert client.verify(poisoned) is False
    assert client.query("What budget did Project Phoenix get?") == []
    assert client.answer("What budget did Project Phoenix get?") == ABSTAIN


def test_contradiction_radar_flags_divergent_facts(client: MemoryClient):
    client.archive("Project Phoenix", "Budget approved at $4.2M for FY26.")
    client.archive("Project Phoenix", "The launch venue is the Berlin office rooftop.")
    found = client.contradictions()
    assert any(c.entity == "Project Phoenix" for c in found)


def test_neighbors_returns_verified_related_nodes(client: MemoryClient):
    child = client.archive("Alice", "Owns Project Phoenix.")
    client.archive(
        "Project Phoenix",
        "Budget approved at $4.2M.",
        relationships=[Relationship(type="owned_by", target_id=child.node_id)],
        node_id="phoenix",
    )
    related = client.neighbors("phoenix", depth=1)
    assert any(n.node_id == child.node_id for n in related)
