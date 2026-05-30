from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cryptomem import MemoryClient, Settings
from cryptomem.adapters.mock_adapter import MockAdapter
from cryptomem.crypto.signer import Signer
from cryptomem.server.app import create_app
from cryptomem.store.sqlite_store import SqliteStore


@pytest.fixture
def api() -> TestClient:
    client = MemoryClient(
        settings=Settings(sqlite_path=":memory:"),
        store=SqliteStore(":memory:"),
        signer=Signer.generate(),
    )
    return TestClient(create_app(client=client, adapter=MockAdapter()))


def test_healthz(api: TestClient):
    resp = api.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_memory_crud_and_proof(api: TestClient):
    created = api.post(
        "/cmem/v1/memory",
        json={"entity": "Project Phoenix", "content": "Budget approved at $4.2M for FY26."},
    ).json()
    assert created["verified"] is True
    node_id = created["node_id"]

    fetched = api.get(f"/cmem/v1/memory/{node_id}")
    assert fetched.status_code == 200
    assert fetched.json()["entity"] == "Project Phoenix"

    proof = api.get(f"/cmem/v1/ledger/proof/{node_id}").json()
    assert proof["node_id"] == node_id
    assert proof["merkle_root"]
    assert proof["verified"] is True

    assert api.get("/cmem/v1/memory/missing").status_code == 404


def test_query_endpoint(api: TestClient):
    api.post(
        "/cmem/v1/memory",
        json={"entity": "Project Phoenix", "content": "Budget approved at $4.2M for FY26."},
    )
    body = api.post("/cmem/v1/query", json={"text": "phoenix budget", "top_k": 5}).json()
    assert body["verified_count"] >= 1
    assert body["nodes"]


def test_chat_grounds_and_returns_provenance(api: TestClient):
    api.post(
        "/cmem/v1/memory",
        json={"entity": "Project Phoenix", "content": "Budget approved at $4.2M for FY26."},
    )
    resp = api.post(
        "/api/chat",
        json={
            "model": "qwen2.5:0.5b",
            "messages": [{"role": "user", "content": "What budget did Project Phoenix get?"}],
        },
    ).json()
    assert resp["done"] is True
    assert "4.2M" in resp["message"]["content"]
    assert resp["cryptomem"]["injected_nodes"]
    assert resp["cryptomem"]["verified"] is True


def test_chat_abstains_when_no_memory(api: TestClient):
    resp = api.post(
        "/api/chat",
        json={"model": "qwen2.5:0.5b", "messages": [{"role": "user", "content": "anything?"}]},
    ).json()
    assert resp["cryptomem"]["injected_nodes"] == []
    assert "cannot answer" in resp["message"]["content"].lower()


def test_confidence_endpoint(api: TestClient):
    api.post(
        "/cmem/v1/memory",
        json={"entity": "Project Phoenix", "content": "Budget approved at $4.2M for FY26."},
    )
    body = api.post("/cmem/v1/confidence", json={"text": "phoenix budget", "samples": 3}).json()
    assert body["clusters"] == 1
    assert body["confidence"] == 1.0


def test_verify_endpoint(api: TestClient):
    api.post(
        "/cmem/v1/memory",
        json={"entity": "Project Phoenix", "content": "Budget approved at 4.2M for FY26."},
    )
    body = api.post("/cmem/v1/verify", json={"draft": "Budget approved at 4.2M for FY26."}).json()
    assert body["verdict"] == "verified"
