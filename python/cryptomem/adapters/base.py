from __future__ import annotations

from abc import ABC, abstractmethod


class LLMAdapter(ABC):
    """Uniform completion interface across model backends."""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Return the model completion for ``prompt``."""
