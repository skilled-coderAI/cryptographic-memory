from __future__ import annotations

import json
import sqlite3
import threading

from cryptomem.embeddings.base import cosine_similarity
from cryptomem.models import MemoryNode
from cryptomem.store.base import MemoryStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory (
    node_id       TEXT PRIMARY KEY,
    entity        TEXT NOT NULL,
    content       TEXT NOT NULL,
    relationships TEXT NOT NULL,
    metadata      TEXT NOT NULL,
    embedding     TEXT,
    crypto        TEXT
);
CREATE INDEX IF NOT EXISTS idx_memory_entity ON memory(entity);
"""


class SqliteStore(MemoryStore):
    """Default zero-config store backed by stdlib ``sqlite3``.

    Vector search runs in Python over stored embeddings, which is plenty for
    edge/potato workloads. ``sqlite-vec`` acceleration can be layered in later
    without changing this interface.
    """

    def __init__(self, path: str = ":memory:"):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _row_to_node(row: sqlite3.Row) -> MemoryNode:
        return MemoryNode(
            node_id=row["node_id"],
            entity=row["entity"],
            content=row["content"],
            relationships=json.loads(row["relationships"]),
            metadata=json.loads(row["metadata"]),
            embedding=json.loads(row["embedding"]) if row["embedding"] else None,
            crypto=json.loads(row["crypto"]) if row["crypto"] else None,
        )

    def write(self, node: MemoryNode) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO memory
                    (node_id, entity, content, relationships, metadata, embedding, crypto)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.node_id,
                    node.entity,
                    node.content,
                    json.dumps([r.model_dump() for r in node.relationships]),
                    json.dumps(node.metadata),
                    json.dumps(node.embedding) if node.embedding is not None else None,
                    node.crypto.model_dump_json() if node.crypto else None,
                ),
            )
            self._conn.commit()

    def get(self, node_id: str) -> MemoryNode | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM memory WHERE node_id = ?", (node_id,)
            ).fetchone()
        return self._row_to_node(row) if row else None

    def query(self, embedding: list[float], top_k: int = 5) -> list[tuple[MemoryNode, float]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM memory").fetchall()
        scored: list[tuple[MemoryNode, float]] = []
        for row in rows:
            node = self._row_to_node(row)
            if node.embedding is None:
                continue
            scored.append((node, cosine_similarity(embedding, node.embedding)))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    def neighbors(self, node_id: str, depth: int = 1) -> list[MemoryNode]:
        seen: set[str] = {node_id}
        frontier = [node_id]
        collected: list[MemoryNode] = []
        for _ in range(max(depth, 0)):
            next_frontier: list[str] = []
            for current in frontier:
                node = self.get(current)
                if node is None:
                    continue
                for rel in node.relationships:
                    if rel.target_id in seen:
                        continue
                    seen.add(rel.target_id)
                    target = self.get(rel.target_id)
                    if target is not None:
                        collected.append(target)
                        next_frontier.append(rel.target_id)
            frontier = next_frontier
        return collected

    def all(self) -> list[MemoryNode]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM memory").fetchall()
        return [self._row_to_node(row) for row in rows]
