from __future__ import annotations

import httpx

from cryptomem.adapters.base import LLMAdapter


class OllamaAdapter(LLMAdapter):
    """Completion adapter that forwards prompts to a local Ollama server.

    Speaks Ollama's native ``/api/generate`` wire protocol with streaming
    disabled, so it works against any stock Ollama install with zero config.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:0.5b",
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def complete(self, prompt: str) -> str:
        resp = self._client.post(
            "/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        return str(resp.json().get("response", ""))

    def is_alive(self) -> bool:
        """Return ``True`` if the Ollama server answers ``GET /api/tags``."""
        try:
            return self._client.get("/api/tags").status_code == 200
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        self._client.close()
