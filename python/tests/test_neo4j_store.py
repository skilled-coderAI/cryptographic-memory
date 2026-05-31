"""Neo4jStore tests using a fake in-memory Bolt driver.

No live Neo4j server is required: a tiny fake driver interprets the exact Cypher
the store emits, which lets us validate parameter serialization, record→node
mapping, and graph traversal deterministically. A separate test covers the
helpful error raised when the optional ``neo4j`` driver is not installed.
"""

import builtins
import re

import pytest

from cryptomem import MemoryClient, Settings
from cryptomem.crypto.signer import Signer
from cryptomem.models import Relationship
from cryptomem.store.neo4j_store import Neo4jStore


class _FakeSession:
    def __init__(self, driver: "FakeNeo4jDriver"):
        self._driver = driver

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def run(self, query: str, **params: object) -> list[dict]:
        return self._driver.handle(query, params)


class FakeNeo4jDriver:
    """Minimal graph engine understanding the store's fixed Cypher statements."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: list[tuple[str, str, str]] = []
        self.queries: list[tuple[str, dict]] = []

    def session(self, database: str | None = None) -> _FakeSession:
        return _FakeSession(self)

    def close(self) -> None:
        pass

    def handle(self, query: str, params: dict) -> list[dict]:
        q = " ".join(query.split())
        self.queries.append((q, params))

        if q.startswith("CREATE CONSTRAINT"):
            return []
        if "SET m.entity" in q:
            self.nodes[params["node_id"]] = {
                "node_id": params["node_id"],
                "entity": params["entity"],
                "content": params["content"],
                "relationships": params["relationships"],
                "metadata": params["metadata"],
                "embedding": params["embedding"],
                "crypto": params["crypto"],
                "rel_targets": params["rel_targets"],
            }
            return []
        if "DELETE r" in q:
            nid = params["node_id"]
            self.edges = [e for e in self.edges if e[0] != nid]
            return []
        if "UNWIND $rels AS rel" in q:
            nid = params["node_id"]
            for rel in params["rels"]:
                if rel["target"] in self.nodes:
                    self.edges.append((nid, rel["type"], rel["target"]))
            return []
        if "s.rel_targets" in q:  # back-fill incoming edges
            nid = params["node_id"]
            for sid, props in self.nodes.items():
                if sid == nid:
                    continue
                for rt in props.get("rel_targets") or []:
                    typ, tgt = rt.split("|", 1)
                    if tgt == nid:
                        self.edges.append((sid, typ, nid))
            return []
        if "RETURN DISTINCT t" in q:
            nid = params["node_id"]
            match = re.search(r"\*1\.\.(\d+)", q)
            depth = int(match.group(1)) if match else 1
            seen: set[str] = set()
            frontier = [nid]
            out: list[str] = []
            for _ in range(depth):
                nxt: list[str] = []
                for cur in frontier:
                    for src, _typ, dst in self.edges:
                        if src == cur and dst not in seen:
                            seen.add(dst)
                            out.append(dst)
                            nxt.append(dst)
                frontier = nxt
            return [{"t": self.nodes[d]} for d in out if d in self.nodes]
        if q.startswith("MATCH (m:Memory) RETURN m"):
            return [{"m": props} for props in self.nodes.values()]
        if "RETURN m" in q:  # get by node_id
            nid = params["node_id"]
            return [{"m": self.nodes[nid]}] if nid in self.nodes else []
        return []


def _client_on_fake() -> tuple[MemoryClient, Neo4jStore]:
    store = Neo4jStore(driver=FakeNeo4jDriver())
    client = MemoryClient(
        settings=Settings(sqlite_path=":memory:"),
        store=store,
        signer=Signer.generate(),
    )
    return client, store


def test_neo4j_store_round_trips_signed_nodes():
    client, store = _client_on_fake()
    node = client.archive("Project Phoenix", "Budget approved at 4.2M for FY26.")

    fetched = store.get(node.node_id)
    assert fetched is not None
    assert fetched.entity == "Project Phoenix"
    assert client.verify(fetched)


def test_neo4j_store_vector_query_ranks_relevant_node():
    client, _ = _client_on_fake()
    client.archive("Project Phoenix", "Budget approved at 4.2M for FY26.")
    client.archive("Lunch Menu", "Tacos on Tuesday.")

    hits = client.query("phoenix budget", top_k=2)
    assert hits
    assert hits[0].node.entity == "Project Phoenix"


def test_neo4j_store_traverses_relationship_edges():
    client, store = _client_on_fake()
    alice = client.archive("Alice", "Leads the platform team.")
    phoenix = client.archive(
        "Project Phoenix",
        "Budget approved at 4.2M.",
        relationships=[Relationship(type="owned_by", target_id=alice.node_id)],
    )

    neighbors = store.neighbors(phoenix.node_id, depth=1)
    assert any(n.node_id == alice.node_id for n in neighbors)
    assert store.neighbors(phoenix.node_id, depth=0) == []


def test_neo4j_store_requires_extra(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "neo4j" or name.startswith("neo4j."):
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match="cryptomem\\[neo4j\\]"):
        Neo4jStore()
