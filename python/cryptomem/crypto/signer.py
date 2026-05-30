from __future__ import annotations

from pathlib import Path

from nacl.encoding import HexEncoder
from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey


class Signer:
    """Ed25519 signer/verifier over hex content digests."""

    def __init__(self, signing_key: SigningKey):
        self._sk = signing_key
        self.verify_key: VerifyKey = signing_key.verify_key

    @property
    def public_key_hex(self) -> str:
        """Hex-encoded public key, used as the envelope's ``public_key_ref``."""
        return self.verify_key.encode(encoder=HexEncoder).decode()

    def sign(self, digest_hex: str) -> str:
        """Sign a hex digest and return the hex-encoded signature."""
        return self._sk.sign(digest_hex.encode(), encoder=HexEncoder).signature.decode()

    @staticmethod
    def verify(pubkey_hex: str, digest_hex: str, signature_hex: str) -> bool:
        """Return ``True`` only if the signature authenticates the digest."""
        try:
            VerifyKey(pubkey_hex.encode(), encoder=HexEncoder).verify(
                digest_hex.encode(), bytes.fromhex(signature_hex)
            )
            return True
        except (BadSignatureError, ValueError):
            return False

    @classmethod
    def generate(cls) -> Signer:
        """Create a signer backed by a fresh in-memory key (ideal for tests)."""
        return cls(SigningKey.generate())

    @classmethod
    def from_key_file(cls, path: str | Path) -> Signer:
        """Load a signer from a hex seed file, generating and persisting one if absent."""
        key_path = Path(path)
        if key_path.exists():
            seed = bytes.fromhex(key_path.read_text().strip())
            return cls(SigningKey(seed))
        sk = SigningKey.generate()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(sk.encode(encoder=HexEncoder).decode())
        return cls(sk)
