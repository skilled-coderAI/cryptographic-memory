from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from nacl.signing import SigningKey

from cryptomem import MemoryClient, Settings
from cryptomem.adapters.mock_adapter import MockAdapter
from cryptomem.crypto.keys import EnvKeyProvider, build_signer
from cryptomem.crypto.merkle import merkle_proof, merkle_root, verify_proof
from cryptomem.crypto.signer import Signer
from cryptomem.server.app import create_app
from cryptomem.store.remote_store import RemoteStore
from cryptomem.store.sqlite_store import SqliteStore


def _remote_backed_client() -> MemoryClient:
    backend = MemoryClient(
        settings=Settings(sqlite_path=":memory:"),
        store=SqliteStore(":memory:"),
        signer=Signer.generate(),
    )
    tc = TestClient(create_app(client=backend, adapter=MockAdapter()))
    remote = RemoteStore("http://testserver", client=tc)
    return MemoryClient(
        settings=Settings(sqlite_path=":memory:"),
        store=remote,
        signer=Signer.generate(),
    )


def test_merkle_inclusion_proof_validates():
    leaves = [f"{i:064x}" for i in range(5)]
    root = merkle_root(leaves)
    assert root is not None
    for i, leaf in enumerate(leaves):
        assert verify_proof(leaf, merkle_proof(leaves, i), root)


def test_merkle_proof_rejects_tampered_leaf():
    leaves = [f"{i:064x}" for i in range(4)]
    root = merkle_root(leaves)
    assert root is not None
    assert not verify_proof("00" * 32, merkle_proof(leaves, 1), root)


def test_client_proof_is_a_verifiable_inclusion_proof(client: MemoryClient):
    a = client.archive("A", "alpha fact one")
    client.archive("B", "beta fact two")
    client.archive("C", "gamma fact three")
    proof = client.proof(a.node_id)
    assert proof is not None
    assert proof["included"] is True
    assert proof["verified"] is True
    assert proof["ledger_root"] == client.ledger_root()


def test_byok_env_provider_is_deterministic(monkeypatch):
    seed = bytes(SigningKey.generate()).hex()
    monkeypatch.setenv("CRYPTOMEM_TEST_SEED", seed)
    settings = Settings(
        byok_provider="env", signing_seed_env="CRYPTOMEM_TEST_SEED", sqlite_path=":memory:"
    )
    signer = build_signer(settings)
    again = EnvKeyProvider("CRYPTOMEM_TEST_SEED").get_signer()
    assert signer.public_key_hex == again.public_key_hex


def test_byok_env_provider_missing_raises(monkeypatch):
    monkeypatch.delenv("CRYPTOMEM_MISSING_SEED", raising=False)
    with pytest.raises(RuntimeError):
        EnvKeyProvider("CRYPTOMEM_MISSING_SEED").get_signer()


def test_remote_store_round_trips_signed_nodes():
    client = _remote_backed_client()
    node = client.archive("Project Phoenix", "Budget approved at 4.2M for FY26.")

    fetched = client.store.get(node.node_id)
    assert fetched is not None
    assert fetched.entity == "Project Phoenix"
    assert client.verify(fetched)

    hits = client.query("phoenix budget", top_k=3)
    assert hits
    assert hits[0].node.entity == "Project Phoenix"


def test_remote_mode_falls_back_to_sqlite_when_backend_down():
    settings = Settings(mode="remote", backend_url="http://127.0.0.1:9", sqlite_path=":memory:")
    client = MemoryClient(settings=settings, signer=Signer.generate())
    assert isinstance(client.store, SqliteStore)
