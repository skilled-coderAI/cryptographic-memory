from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from nacl.signing import SigningKey

from cryptomem.crypto.signer import Signer

if TYPE_CHECKING:
    from cryptomem.config import Settings


class KeyProvider(ABC):
    """Pluggable source of the Ed25519 signing key (BYOK seam).

    Lets deployments keep the private key wherever policy dictates — a local
    file for dev, an environment-injected seed for containers, or (via a custom
    provider) a KMS/Vault integration — without the engine ever hard-coding key
    storage.
    """

    @abstractmethod
    def get_signer(self) -> Signer:
        """Return a ready-to-use :class:`Signer`."""


class LocalFileKeyProvider(KeyProvider):
    """Load (or generate-and-persist) a hex seed on the local filesystem."""

    def __init__(self, path: str):
        self.path = path

    def get_signer(self) -> Signer:
        return Signer.from_key_file(self.path)


class EnvKeyProvider(KeyProvider):
    """Read a hex-encoded Ed25519 seed from an environment variable.

    Suited to containerised/secret-manager workflows where the key is injected
    at runtime and never written to disk.
    """

    def __init__(self, env_var: str):
        self.env_var = env_var

    def get_signer(self) -> Signer:
        seed = os.environ.get(self.env_var)
        if not seed:
            raise RuntimeError(f"BYOK env provider: ${self.env_var} is not set")
        return Signer(SigningKey(bytes.fromhex(seed.strip())))


def build_signer(settings: Settings) -> Signer:
    """Resolve a :class:`Signer` from ``settings.byok_provider``."""
    provider = (settings.byok_provider or "file").lower()
    if provider == "file":
        return LocalFileKeyProvider(settings.signing_key_path).get_signer()
    if provider == "env":
        return EnvKeyProvider(settings.signing_seed_env).get_signer()
    raise ValueError(f"unknown byok_provider: {settings.byok_provider!r}")
