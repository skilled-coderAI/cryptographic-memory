from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptomem import MemoryClient
from cryptomem.models import Relationship
from cryptomem.proactive import extract_facts


def test_extract_facts_keeps_declarative_statements():
    text = "Project Phoenix shipped in Q3 2025. What is the budget? ok."
    facts = extract_facts(text)
    assert any("Project Phoenix shipped" in f for f in facts)
    assert all("?" not in f for f in facts)
    assert all(f != "ok." for f in facts)


def test_planner_suggests_unused_neighbors(client: MemoryClient):
    alice = client.archive("Alice", "Leads the platform team.")
    phoenix = client.archive(
        "Project Phoenix",
        "Budget approved at 4.2M.",
        relationships=[Relationship(type="owned_by", target_id=alice.node_id)],
    )
    suggestions = client.suggest([phoenix])
    assert suggestions[0]["node_id"] == alice.node_id
    assert "owned_by" in suggestions[0]["reason"]


def test_writeback_stages_pending_then_confirm(client: MemoryClient):
    staged = client.stage_facts("Project Phoenix shipped in Q3 2025 with a 4.2M budget.")
    assert staged
    pending_ids = {n.node_id for n in client.pending()}
    assert staged[0].node_id in pending_ids
    assert client.verify(staged[0])

    confirmed = client.confirm(staged[0].node_id)
    assert confirmed is not None
    assert confirmed.metadata["status"] == "confirmed"
    assert client.verify(confirmed)
    assert staged[0].node_id not in {n.node_id for n in client.pending()}


def test_confirm_unknown_returns_none(client: MemoryClient):
    assert client.confirm("does-not-exist") is None


def test_triggers_flag_expired_and_link_gap(client: MemoryClient):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    node = client.archive("Token", "Rotates daily.", metadata={"expires_at": past})
    suggestions = client.triggers()
    types = {s["type"] for s in suggestions if s.get("node_id") == node.node_id}
    assert "refresh" in types
    assert "link_gap" in types


def test_triggers_flag_contradiction(client: MemoryClient):
    client.archive("Server", "The primary region is us-east-1.")
    client.archive("Server", "Bananas are a yellow tropical fruit grown near the equator.")
    assert any(s["type"] == "reconcile" for s in client.triggers())
