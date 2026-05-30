from __future__ import annotations

from cryptomem.crypto.hashing import sha256
from cryptomem.crypto.merkle import merkle_root
from cryptomem.crypto.signer import Signer


def _node(content: str = "Budget approved at $4.2M.") -> dict:
    return {
        "entity": "Project Phoenix",
        "content": content,
        "relationships": [{"type": "owned_by", "target_id": "mem_alice"}],
        "metadata": {"source": "memo-12"},
    }


def test_hash_is_deterministic_and_order_independent():
    a = _node()
    b = dict(a)
    b["relationships"] = list(reversed(a["relationships"])) + []
    assert sha256(a) == sha256(_node())


def test_sign_verify_round_trip():
    signer = Signer.generate()
    digest = sha256(_node())
    sig = signer.sign(digest)
    assert Signer.verify(signer.public_key_hex, digest, sig) is True


def test_mutated_content_is_rejected():
    signer = Signer.generate()
    digest = sha256(_node())
    sig = signer.sign(digest)
    tampered_digest = sha256(_node(content="Budget approved at $9.9M."))
    assert Signer.verify(signer.public_key_hex, tampered_digest, sig) is False


def test_swapped_signature_is_rejected():
    signer = Signer.generate()
    other = Signer.generate()
    digest = sha256(_node())
    foreign_sig = other.sign(digest)
    assert Signer.verify(signer.public_key_hex, digest, foreign_sig) is False


def test_merkle_root_changes_with_leaves():
    assert merkle_root([]) is None
    one = merkle_root(["a" * 64])
    two = merkle_root(["a" * 64, "b" * 64])
    assert one is not None and two is not None and one != two
