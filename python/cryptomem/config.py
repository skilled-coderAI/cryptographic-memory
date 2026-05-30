from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration, overridable via ``CRYPTOMEM_*`` env vars or ``.env``."""

    model_config = SettingsConfigDict(env_prefix="CRYPTOMEM_", env_file=".env", extra="ignore")

    profile: str = "potato"
    mode: str = "sqlite"
    sqlite_path: str = ":memory:"
    ollama_url: str = "http://localhost:11434"
    default_model: str = "qwen2.5:0.5b"
    embedder: str = "stub"
    backend_url: str | None = None
    backend_api_key: str | None = None
    signing_key_path: str = "./cryptomem.key"
    max_context_tokens: int = 1500
    require_verification: bool = True
    contradiction_threshold: float = 0.6
    enable_citations: bool = False
    citation_min_support: float = 0.2
    enable_faithfulness: bool = False
    faithfulness_threshold: float = 0.25
    entropy_samples: int = 5
    entropy_cluster_threshold: float = 0.8
