"""Neo4j-backed :class:`MemoryStore` with real, idiomatic Cypher.

Memory nodes are stored as ``(:Memory)`` nodes; their typed relationships are
projected onto native ``[:REL {type}]`` edges so the graph can be traversed in
Cypher. Complex fields (relationships/metadata/crypto) are serialized to JSON
property strings, while the embedding is stored as a native list of floats so a
vector index can be layered on later. Vector search itself runs client-side to
keep the contract identical to the SQLite/Remote backends and avoid requiring
GDS/vector-index setup on a fresh database.

The ``neo4j`` driver is imported lazily so the package keeps working without the
optional extra installed.
"""

import json
from typing import Any

from cryptomem.embeddings.base import cosine_similarity
from cryptomem.models import MemoryNode
from cryptomem.store.base import MemoryStore

_INSTALL_HINT = (
    "Neo4jStore requires the 'neo4j' driver. Install it with: pip install 'cryptomem[neo4j]'"
)


class Neo4jStore(MemoryStore):
    """Graph-native store speaking Cypher against a Neo4j (Bolt) endpoint."""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "neo4j",
        database: str = "neo4j",
        driver: Any | None = None,
    ):
        if driver is None:
            try:
                from neo4j import GraphDatabase
            except ModuleNotFoundError as exc:  # pragma: no cover - exercised via guard test
                raise RuntimeError(_INSTALL_HINT) from exc
            driver = GraphDatabase.driver(uri, auth=(user, password))
        self._driver = driver
        self._database = database
        self._ensure_schema()

    def _run(self, query: str, **params: Any) -> list[Any]:
        with self._driver.session(database=self._database) as session:
            return list(session.run(query, **params))

    def _ensure_schema(self) -> None:
        self._run(
            "CREATE CONSTRAINT memory_node_id IF NOT EXISTS "
            "FOR (m:Memory) REQUIRE m.node_id IS UNIQUE"
        )

    @staticmethod
    def _to_node(props: Any) -> MemoryNode:
        data = dict(props)
        embedding = data.get("embedding")
        crypto = data.get("crypto")
        return MemoryNode(
            node_id=data["node_id"],
            entity=data["entity"],
            content=data["content"],
            relationships=json.loads(data.get("relationships") or "[]"),
            metadata=json.loads(data.get("metadata") or "{}"),
            embedding=list(embedding) if embedding is not None else None,
            crypto=json.loads(crypto) if crypto else None,
        )

    def write(self, node: MemoryNode) -> None:
        rels = [{"type": r.type, "target": r.target_id} for r in node.relationships]

        # 1. Upsert the node and all of its scalar/JSON properties.
        self._run(
            """
            MERGE (m:Memory {node_id: $node_id})
            SET m.entity        = $entity,
                m.content       = $content,
                m.relationships = $relationships,
                m.metadata      = $metadata,
                m.embedding     = $embedding,
                m.crypto        = $crypto,
                m.rel_targets   = $rel_targets
            """,
            node_id=node.node_id,
            entity=node.entity,
            content=node.content,
            relationships=json.dumps([r.model_dump() for r in node.relationships]),
            metadata=json.dumps(node.metadata),
            embedding=node.embedding,
            crypto=node.crypto.model_dump_json() if node.crypto else None,
            rel_targets=[f"{r.type}|{r.target_id}" for r in node.relationships],
        )

        # 2. Rebuild this node's outgoing edges so they stay in sync on re-write.
        self._run(
            "MATCH (m:Memory {node_id: $node_id})-[r:REL]->() DELETE r",
            node_id=node.node_id,
        )
        if rels:
            self._run(
                """
                MATCH (m:Memory {node_id: $node_id})
                UNWIND $rels AS rel
                MATCH (t:Memory {node_id: rel.target})
                MERGE (m)-[:REL {type: rel.type}]->(t)
                """,
                node_id=node.node_id,
                rels=rels,
            )

        # 3. Back-fill incoming edges from nodes written earlier that point here.
        self._run(
            """
            MATCH (s:Memory)
            WHERE s.node_id <> $node_id
            UNWIND s.rel_targets AS rt
            WITH s, rt WHERE split(rt, '|')[1] = $node_id
            MATCH (x:Memory {node_id: $node_id})
            MERGE (s)-[:REL {type: split(rt, '|')[0]}]->(x)
            """,
            node_id=node.node_id,
        )

    def get(self, node_id: str) -> MemoryNode | None:
        rows = self._run("MATCH (m:Memory {node_id: $node_id}) RETURN m", node_id=node_id)
        return self._to_node(rows[0]["m"]) if rows else None

    def all(self) -> list[MemoryNode]:
        rows = self._run("MATCH (m:Memory) RETURN m")
        return [self._to_node(row["m"]) for row in rows]

    def query(self, embedding: list[float], top_k: int = 5) -> list[tuple[MemoryNode, float]]:
        scored: list[tuple[MemoryNode, float]] = []
        for node in self.all():
            if node.embedding is None:
                continue
            scored.append((node, cosine_similarity(embedding, node.embedding)))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    def neighbors(self, node_id: str, depth: int = 1) -> list[MemoryNode]:
        if depth < 1:
            return []
        rows = self._run(
            f"MATCH (:Memory {{node_id: $node_id}})-[:REL*1..{int(depth)}]->(t:Memory) "
            "RETURN DISTINCT t",
            node_id=node_id,
        )
        return [self._to_node(row["t"]) for row in rows]

    def close(self) -> None:
        self._driver.close()
