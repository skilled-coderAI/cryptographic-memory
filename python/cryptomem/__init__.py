from cryptomem.adapters.mock_adapter import MockAdapter
from cryptomem.adapters.ollama_adapter import OllamaAdapter
from cryptomem.client import ABSTAIN, MemoryClient
from cryptomem.config import Settings
from cryptomem.embeddings.minilm import MiniLMEmbedder
from cryptomem.embeddings.stub import StubEmbedder
from cryptomem.models import (
    Contradiction,
    CryptoEnvelope,
    MemoryNode,
    Relationship,
    ScoredNode,
)
from cryptomem.verification import (
    ChainOfVerification,
    Citer,
    FaithfulnessChecker,
    GroundingGate,
    SemanticEntropy,
)

__version__ = "0.1.0"

__all__ = [
    "ABSTAIN",
    "MemoryClient",
    "Settings",
    "MemoryNode",
    "Relationship",
    "CryptoEnvelope",
    "ScoredNode",
    "Contradiction",
    "StubEmbedder",
    "MiniLMEmbedder",
    "MockAdapter",
    "OllamaAdapter",
    "GroundingGate",
    "FaithfulnessChecker",
    "Citer",
    "SemanticEntropy",
    "ChainOfVerification",
    "__version__",
]
