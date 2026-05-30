from __future__ import annotations

from pydantic import BaseModel, Field


class Relationship(BaseModel):
    """A typed, directed edge from one memory node to another."""

    type: str
    target_id: str


class CryptoEnvelope(BaseModel):
    """Integrity metadata bound to a memory node at write time."""

    hash: str
    signature: str
    public_key_ref: str
    merkle_root: str | None = None


class MemoryNode(BaseModel):
    """A single relational, verifiable unit of memory."""

    node_id: str
    entity: str
    content: str
    relationships: list[Relationship] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    embedding: list[float] | None = None
    crypto: CryptoEnvelope | None = None


class ScoredNode(BaseModel):
    """A retrieved node paired with its relevance, verification, and confidence."""

    node: MemoryNode
    score: float
    verified: bool
    confidence: float


class Contradiction(BaseModel):
    """Two nodes describing the same entity with divergent content."""

    entity: str
    left_id: str
    right_id: str
    similarity: float
