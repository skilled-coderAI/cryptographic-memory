from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_bytes(node: dict[str, Any]) -> bytes:
    """Serialize the identity-bearing fields of a node deterministically.

    Write-time and read-time serialization must be byte-identical for
    verification to hold, so relationships are sorted and keys are ordered.
    """
    payload = {
        "entity": node["entity"],
        "content": node["content"],
        "relationships": sorted((r["type"], r["target_id"]) for r in node.get("relationships", [])),
        "metadata": node.get("metadata", {}),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sha256(node: dict[str, Any]) -> str:
    """Return the hex SHA-256 digest of a node's canonical bytes."""
    return hashlib.sha256(canonical_bytes(node)).hexdigest()
