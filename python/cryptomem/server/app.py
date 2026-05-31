from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from cryptomem.adapters.base import LLMAdapter
from cryptomem.adapters.ollama_adapter import OllamaAdapter
from cryptomem.client import MemoryClient
from cryptomem.models import MemoryNode, Relationship


class MemoryIn(BaseModel):
    entity: str
    content: str
    relationships: list[Relationship] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class QueryIn(BaseModel):
    text: str
    top_k: int = 5
    depth: int = 0


class ConfidenceIn(BaseModel):
    text: str
    samples: int | None = None
    top_k: int = 5
    depth: int = 0


class VerifyIn(BaseModel):
    draft: str
    top_k: int = 3


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    model: str = "qwen2.5:0.5b"
    messages: list[ChatMessage]
    stream: bool = False


class GenerateIn(BaseModel):
    model: str = "qwen2.5:0.5b"
    prompt: str
    stream: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_app(
    client: MemoryClient | None = None,
    adapter: LLMAdapter | None = None,
    ollama_url: str = "http://localhost:11434",
) -> FastAPI:
    """Build the Ollama-compatible sidecar bound to a memory client + adapter.

    Injecting ``client`` and ``adapter`` keeps the app fully testable offline;
    in production the adapter defaults to a live Ollama server.
    """
    mem = client or MemoryClient()
    llm = adapter or OllamaAdapter(base_url=ollama_url)
    app = FastAPI(title="cryptomem sidecar", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict:
        alive = llm.is_alive() if isinstance(llm, OllamaAdapter) else True
        return {"status": "ok", "ollama": alive}

    @app.get("/api/tags")
    def tags() -> dict:
        if isinstance(llm, OllamaAdapter):
            try:
                resp = llm._client.get("/api/tags")
                resp.raise_for_status()
                return dict(resp.json())
            except Exception:
                return {"models": []}
        return {"models": []}

    @app.post("/api/chat")
    def chat(body: ChatIn) -> dict:
        question = next((m.content for m in reversed(body.messages) if m.role == "user"), "")
        text, provenance = mem.respond(question, adapter=llm)
        return {
            "model": body.model,
            "created_at": _now(),
            "message": {"role": "assistant", "content": text},
            "done": True,
            "cryptomem": provenance,
        }

    @app.post("/api/generate")
    def generate(body: GenerateIn) -> dict:
        text, provenance = mem.respond(body.prompt, adapter=llm)
        return {
            "model": body.model,
            "created_at": _now(),
            "response": text,
            "done": True,
            "cryptomem": provenance,
        }

    @app.post("/cmem/v1/memory")
    def add_memory(body: MemoryIn) -> dict:
        node = mem.archive(
            entity=body.entity,
            content=body.content,
            relationships=body.relationships,
            metadata=body.metadata,
        )
        return {**node.model_dump(), "verified": mem.verify(node)}

    @app.post("/cmem/v1/memory/signed")
    def add_signed(node: MemoryNode) -> dict:
        if not mem.verify(node):
            raise HTTPException(status_code=422, detail="node failed verification")
        mem.store.write(node)
        return {**node.model_dump(), "verified": True}

    @app.get("/cmem/v1/memory")
    def list_memory() -> dict:
        return {"nodes": [n.model_dump() for n in mem.store.all()]}

    @app.get("/cmem/v1/memory/pending")
    def pending() -> dict:
        return {"nodes": [n.model_dump() for n in mem.pending()]}

    @app.get("/cmem/v1/memory/{node_id}")
    def get_memory(node_id: str) -> dict:
        node = mem.store.get(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        return {**node.model_dump(), "verified": mem.verify(node)}

    @app.post("/cmem/v1/query")
    def query(body: QueryIn) -> dict:
        scored = mem.query(body.text, top_k=body.top_k, depth=body.depth)
        return {
            "nodes": [s.node.model_dump() for s in scored],
            "verified_count": sum(1 for s in scored if s.verified),
            "confidences": [s.confidence for s in scored],
        }

    @app.post("/cmem/v1/confidence")
    def confidence(body: ConfidenceIn) -> dict:
        return mem.confidence(
            body.text, adapter=llm, samples=body.samples, top_k=body.top_k, depth=body.depth
        )

    @app.post("/cmem/v1/verify")
    def verify(body: VerifyIn) -> dict:
        return mem.verify_answer(body.draft, top_k=body.top_k)

    @app.get("/cmem/v1/triggers")
    def triggers() -> dict:
        return {"suggestions": mem.triggers()}

    @app.post("/cmem/v1/memory/{node_id}/confirm")
    def confirm(node_id: str) -> dict:
        node = mem.confirm(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="no pending node with that id")
        return {**node.model_dump(), "verified": mem.verify(node)}

    @app.get("/cmem/v1/memory/{node_id}/neighbors")
    def neighbors(node_id: str, depth: int = 1) -> dict:
        return {"nodes": [n.model_dump() for n in mem.neighbors(node_id, depth=depth)]}

    @app.get("/cmem/v1/ledger/proof/{node_id}")
    def proof(node_id: str) -> dict:
        result = mem.proof(node_id)
        if result is None:
            raise HTTPException(status_code=404, detail="node not found")
        return result

    return app
