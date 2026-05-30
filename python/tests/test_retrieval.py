from __future__ import annotations

from cryptomem import MemoryClient
from cryptomem.models import Relationship
from cryptomem.retrieval import extract_entities


def test_extract_entities_finds_proper_nouns():
    ents = extract_entities("What budget did Project Phoenix get from Alice?")
    assert "Project Phoenix" in ents
    assert "Alice" in ents


def test_retrieve_ranks_relevant_first(client: MemoryClient):
    client.archive("Project Phoenix", "Budget approved at $4.2M for FY26.")
    client.archive("Dragon", "Ship date slipped to Q4.")
    hits = client.query("phoenix budget", top_k=2)
    assert hits[0].node.entity == "Project Phoenix"
    assert hits[0].score >= hits[-1].score


def test_graph_expansion_pulls_in_neighbors(client: MemoryClient):
    alice = client.archive("Alice", "Owns and manages Project Phoenix.")
    client.archive(
        "Project Phoenix",
        "Budget approved at $4.2M.",
        relationships=[Relationship(type="owned_by", target_id=alice.node_id)],
        node_id="phoenix",
    )
    no_expand = {s.node.node_id for s in client.query("phoenix budget", top_k=1, depth=0)}
    expanded = {s.node.node_id for s in client.query("phoenix budget", top_k=1, depth=1)}
    assert "phoenix" in no_expand
    assert alice.node_id in expanded
    assert alice.node_id not in no_expand
