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


def merkle_proof(leaves: list[str], index: int) -> list[tuple[str, str]]:
    """Return the audit path proving ``leaves[index]`` is in the tree.

    Each step is ``(sibling_hash, position)`` where ``position`` is ``"L"`` or
    ``"R"`` (the side the sibling sits on). Mirrors :func:`merkle_root`'s
    odd-level duplication so proofs validate against the same root.
    """
    if not leaves or index < 0 or index >= len(leaves):
        return []
    proof: list[tuple[str, str]] = []
    level = list(leaves)
    idx = index
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        if idx % 2 == 0:
            proof.append((level[idx + 1], "R"))
        else:
            proof.append((level[idx - 1], "L"))
        idx //= 2
        level = [_hash_pair(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return proof


def verify_proof(leaf: str, proof: list[tuple[str, str]], root: str) -> bool:
    """Re-fold ``leaf`` up the audit ``proof`` and check it equals ``root``."""
    computed = leaf
    for sibling, position in proof:
        if position == "R":
            computed = _hash_pair(computed, sibling)
        else:
            computed = _hash_pair(sibling, computed)
    return computed == root
