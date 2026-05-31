# cryptomem

Cryptographically verified, relational, persistent memory for AI agents.

This package is the Python engine. Every fact is SHA-256 hashed and Ed25519
signed at write time; at read time each node is re-verified, and tampered or
unsigned facts are dropped so the agent abstains rather than guessing.

```python
from cryptomem import MemoryClient

mem = MemoryClient()
mem.archive("Project Phoenix", "Budget approved at $4.2M for FY26.")

for hit in mem.query("What budget did Project Phoenix get?"):
    print(hit.node.content, hit.confidence)

print(mem.answer("What budget did Project Phoenix get?"))
```

Runs on CPU-only hardware with zero model downloads via the default stub
embedder and in-memory SQLite store. See the repository `docs/` for the full
architecture and roadmap.

## Beyond retrieval

- `mem.respond(...)` — answer plus a provenance block (injected node ids,
  verification status, Merkle root).
- `mem.proof(node_id)` — a verifiable Merkle **inclusion proof** against the
  current ledger root.
- `mem.confidence(...)` — semantic-entropy confidence over sampled answers.
- `mem.verify_answer(draft)` — Chain-of-Verification re-check of a draft.
- `mem.contradictions()` — same-entity nodes whose content diverges.
- `mem.suggest(...)`, `mem.triggers()`, `mem.stage_facts(...)`,
  `mem.pending()`, `mem.confirm(node_id)` — proactive planner, triggers, and
  write-back of staged (pending) facts that you later confirm.

## Store backends

Selected via `CRYPTOMEM_MODE` (or `Settings(mode=...)`):

- **`sqlite`** (default) — zero-config local store; Python-side vector search.
- **`neo4j`** — graph-native store over the Bolt driver
  (`pip install "cryptomem[neo4j]"`, `CRYPTOMEM_NEO4J_URI=...`).
- **`remote`** — signs locally and POSTs verbatim to a `/cmem/v1/*` backend
  (`CRYPTOMEM_BACKEND_URL=...`); falls back to SQLite if the backend is down.

## Optional extras

`pip install "cryptomem[local]"` (MiniLM embeddings), `[serve]` (FastAPI
Ollama-compatible sidecar + CLI), `[neo4j]` (graph store), `[dev]` (tooling).
