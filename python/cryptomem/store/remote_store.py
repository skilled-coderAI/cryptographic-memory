from __future__ import annotations

import httpx

from cryptomem.embeddings.base import cosine_similarity
from cryptomem.models import MemoryNode
from cryptomem.store.base import MemoryStore


def _strip_extras(payload: dict) -> dict:
    """Drop server-added annotation keys so the body parses as a MemoryNode."""
    return {k: v for k, v in payload.items() if k in MemoryNode.model_fields}


class RemoteStore(MemoryStore):
    """Talks the ``/cmem/v1/*`` wire protocol to a remote ledger/graph service.

    Nodes are signed locally and POSTed verbatim, so the backend stores
    already-verifiable facts (zero-trust). Vector search is performed
    client-side over the fetched node set, keeping the embedding-based
    :class:`MemoryStore` contract identical to the local SQLite backend.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 15.0,
        client: httpx.Client | None = None,
    ):
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout
        )

    def healthz(self) -> bool:
        """Return ``True`` if the backend answers ``GET /healthz``."""
        try:
            return self._client.get("/healthz").status_code == 200
        except httpx.HTTPError:
            return False

    def write(self, node: MemoryNode) -> None:
        resp = self._client.post("/cmem/v1/memory/signed", json=node.model_dump())
        resp.raise_for_status()

    def get(self, node_id: str) -> MemoryNode | None:
        resp = self._client.get(f"/cmem/v1/memory/{node_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return MemoryNode(**_strip_extras(resp.json()))

    def all(self) -> list[MemoryNode]:
        resp = self._client.get("/cmem/v1/memory")
        resp.raise_for_status()
        return [MemoryNode(**_strip_extras(n)) for n in resp.json()["nodes"]]

    def query(self, embedding: list[float], top_k: int = 5) -> list[tuple[MemoryNode, float]]:
        scored: list[tuple[MemoryNode, float]] = []
        for node in self.all():
            if node.embedding is None:
                continue
            scored.append((node, cosine_similarity(embedding, node.embedding)))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    def neighbors(self, node_id: str, depth: int = 1) -> list[MemoryNode]:
        resp = self._client.get(f"/cmem/v1/memory/{node_id}/neighbors", params={"depth": depth})
        resp.raise_for_status()
        return [MemoryNode(**_strip_extras(n)) for n in resp.json()["nodes"]]

    def close(self) -> None:
        self._client.close()
