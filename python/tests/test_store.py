from __future__ import annotations

from cryptomem.embeddings.stub import StubEmbedder
from cryptomem.models import MemoryNode, Relationship
from cryptomem.store.sqlite_store import SqliteStore


def _emb(text: str) -> list[float]:
    return StubEmbedder().embed(text)


def test_write_get_round_trip():
    store = SqliteStore(":memory:")
    node = MemoryNode(node_id="n1", entity="Phoenix", content="budget 4.2M")
    store.write(node)
    fetched = store.get("n1")
    assert fetched is not None
    assert fetched.entity == "Phoenix"
    assert fetched.content == "budget 4.2M"


def test_query_ranks_by_similarity():
    store = SqliteStore(":memory:")
    store.write(
        MemoryNode(
            node_id="n1",
            entity="Phoenix",
            content="budget approved",
            embedding=_emb("budget approved"),
        )
    )
    store.write(
        MemoryNode(
            node_id="n2",
            entity="Dragon",
            content="ship date slipped",
            embedding=_emb("ship date slipped"),
        )
    )
    ranked = store.query(_emb("what is the budget"), top_k=2)
    assert ranked[0][0].node_id == "n1"
    assert ranked[0][1] >= ranked[1][1]


def test_neighbors_traversal():
    store = SqliteStore(":memory:")
    store.write(
        MemoryNode(
            node_id="a",
            entity="A",
            content="root",
            relationships=[Relationship(type="links", target_id="b")],
        )
    )
    store.write(
        MemoryNode(
            node_id="b",
            entity="B",
            content="child",
            relationships=[Relationship(type="links", target_id="c")],
        )
    )
    store.write(MemoryNode(node_id="c", entity="C", content="grandchild"))

    depth1 = {n.node_id for n in store.neighbors("a", depth=1)}
    depth2 = {n.node_id for n in store.neighbors("a", depth=2)}
    assert depth1 == {"b"}
    assert depth2 == {"b", "c"}
