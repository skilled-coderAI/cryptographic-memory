"""Web view for the cryptomem verified-database agent (manus.im-style UI).

Serves a single-page chat UI where you ask plain-English questions about a small
sales/CRM **SQLite database** and a local Ollama model answers -- grounded in
cryptographically verified facts derived from that database. No SQL is ever
generated or run to answer you: at startup the database is mirrored into signed
cryptomem nodes, and the agent answers only from signature-verified data (or
abstains). An optional "Reasoning" panel streams the live pipeline trace --
understand, recall verified DB facts, signature verification, grounding gate,
synthesize -- so you can *see* how a database row becomes a trusted answer.

You can also speak your question (microphone button) and have answers read back
(Speak toggle); the typed path is fully functional on its own.

Run it::

    ollama serve                                   # qwen3.5:0.8b pulled locally
    pip install "cryptomem[serve,local,agno]" ollama
    python "examples/database example/server.py"
    # open http://127.0.0.1:8200

Config (all optional):
    AGNO_MODEL            Ollama model id            (default: qwen3.5:0.8b)
    CRYPTOMEM_OLLAMA_URL  Ollama base URL            (default: http://localhost:11434)
    MEM_EMBEDDER          stub | minilm              (default: stub; minilm strongly advised here)
    MEM_NUM_CTX           model context window       (default: 2048; smaller = less RAM)
    MEM_MIN_CONFIDENCE    grounding relevance gate   (default: 0.30)
    CRYPTOMEM_*           memory backend (sqlite / neo4j / remote ledger URL)
"""

from __future__ import annotations

import json
import queue
import threading
from pathlib import Path

import db_agent as agent_mod
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from cryptomem.adapters.ollama_adapter import OllamaAdapter

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="cryptomem verified-database web view", version="0.1.0")


class ChatIn(BaseModel):
    message: str


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    agent_mod.get_memory()  # ensure DB seeded + facts archived + embedder resolved
    probe = OllamaAdapter(base_url=agent_mod.OLLAMA_HOST, model=agent_mod.MODEL_ID)
    alive = probe.is_alive()
    probe.close()
    return {
        "model": agent_mod.MODEL_ID,
        "host": agent_mod.OLLAMA_HOST,
        "ollama_alive": alive,
        "embedder": agent_mod.embedder_label(),
        "min_confidence": agent_mod.MIN_CONFIDENCE,
        "fact_count": len(agent_mod.list_facts()),
    }


@app.get("/api/schema")
def schema() -> dict:
    return {"tables": agent_mod.schema_summary()}


@app.get("/api/memory")
def memory() -> dict:
    return {"facts": agent_mod.list_facts()}


@app.post("/api/chat")
def chat(body: ChatIn) -> StreamingResponse:
    """Run the agno agent and stream the reasoning trace + final answer via SSE."""
    q: queue.Queue = queue.Queue()
    provenance: dict = {}

    def recall_database_facts(query: str) -> str:
        """Retrieve cryptographically verified sales-database facts relevant to `query`.

        Only signature-verified, sufficiently relevant facts derived from the
        sales database are returned. If nothing verified matches,
        NO_VERIFIED_MEMORY is returned and you MUST abstain. Cite the node ids in
        square brackets.
        """
        q.put({"type": "tool_call", "name": "recall_database_facts", "query": query})
        facts_block, prov = agent_mod.run_pipeline(query, emit=q.put)
        provenance.clear()
        provenance.update(prov)
        return facts_block

    def worker() -> None:
        try:
            q.put({"type": "status", "label": "Agent reading your question"})
            try:
                agent = agent_mod.build_agent(recall_database_facts)
            except ModuleNotFoundError as exc:
                q.put(
                    {
                        "type": "error",
                        "message": f"agno/ollama not installed: {exc}. "
                        'Run: pip install "cryptomem[agno]" ollama',
                    }
                )
                return
            result = agent.run(body.message)
            answer = getattr(result, "content", None) or str(result)
            q.put({"type": "answer", "content": answer, "provenance": dict(provenance)})
        except Exception as exc:  # noqa: BLE001 - surface any runtime error to the UI
            q.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            event = q.get()
            if event is None:
                yield _sse({"type": "done"})
                break
            yield _sse(event)

    return StreamingResponse(stream(), media_type="text/event-stream")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8200)
