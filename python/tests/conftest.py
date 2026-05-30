from __future__ import annotations

import pytest

from cryptomem import MemoryClient, Settings
from cryptomem.crypto.signer import Signer
from cryptomem.store.sqlite_store import SqliteStore


@pytest.fixture
def client() -> MemoryClient:
    settings = Settings(sqlite_path=":memory:", require_verification=True)
    return MemoryClient(settings=settings, store=SqliteStore(":memory:"), signer=Signer.generate())
