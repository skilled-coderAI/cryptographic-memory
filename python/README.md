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
