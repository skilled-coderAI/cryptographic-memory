from __future__ import annotations

import hashlib


def _hash_pair(left: str, right: str) -> str:
    return hashlib.sha256(f"{left}{right}".encode()).hexdigest()


def merkle_root(leaves: list[str]) -> str | None:
    """Compute a SHA-256 Merkle root over leaf hex digests.

    Returns ``None`` for an empty list. Odd levels duplicate the last node,
    yielding a deterministic, locally verifiable provenance anchor without any
    external ledger.
    """
    if not leaves:
        return None
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [_hash_pair(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]
