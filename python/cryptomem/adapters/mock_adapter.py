from __future__ import annotations

from cryptomem.adapters.base import LLMAdapter


class MockAdapter(LLMAdapter):
    """Model-free adapter for deterministic, offline development and tests.

    Echoes the verified context it was handed so grounding and abstention can
    be asserted without downloading or running any model.
    """

    def complete(self, prompt: str) -> str:
        return f"[mock] grounded answer based on:\n{prompt.strip()}"
