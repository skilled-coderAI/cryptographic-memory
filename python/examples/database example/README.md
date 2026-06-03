# Verified database agent (cryptomem + local AI)

Ask a small sales/CRM **SQLite database** questions in plain English and get
answers from a **local Ollama model** that are grounded in *cryptographically
verified* facts derived from that database. No SQL is generated or executed to
answer you: at startup the database is mirrored into signed `cryptomem` nodes,
and the agent answers **only** from signature-verified data (or abstains).

It mirrors the [`detailed example`](../detailed%20example/) UI, adds a live
**Reasoning** pipeline panel (understand → recall verified DB facts → verify →
ground → synthesize), and supports **voice**: a microphone button for
speech-to-text and a **Speak** toggle to read answers aloud (the typed path is
fully functional on its own).

## Run it

```cmd
ollama serve
pip install "cryptomem[serve,local,agno]" ollama
python "examples/database example/server.py"
```

Then open <http://127.0.0.1:8200>.

## Recommended: use the MiniLM embedder

The example runs with the lightweight, zero-RAM **stub** embedder by default so
it works on small machines. The stub is hash-based, so on this dataset (many
similar-sounding sales facts) it can mis-rank results and may *not* abstain on
out-of-scope questions such as the *"2030 forecast"* prompt.

For accurate semantic retrieval — and correct abstention on questions the
database can't answer — set the MiniLM embedder before starting the server:

```cmd
set MEM_EMBEDDER=minilm
python "examples/database example/server.py"
```

This requires the `local` extra (already included in the install command above)
and downloads a small model on first use.

## Try these questions

- *What kind of sales effort happened in Q2?*
- *Who was the top sales rep this year?*
- *How much revenue did the West region close?*
- *What is our revenue forecast for 2030?* — should abstain (no verified data)

## Configuration (all optional)

| Variable | Default | Description |
| --- | --- | --- |
| `AGNO_MODEL` | `qwen3.5:0.8b` | Ollama model id |
| `CRYPTOMEM_OLLAMA_URL` | `http://localhost:11434` | Ollama base URL |
| `MEM_EMBEDDER` | `stub` | `stub` (low-RAM) or `minilm` (semantic; recommended) |
| `MEM_NUM_CTX` | `2048` | Model context window (smaller = less RAM) |
| `MEM_MIN_CONFIDENCE` | `0.30` | Grounding relevance gate |
| `CRYPTOMEM_*` | — | Memory backend (sqlite / neo4j / remote ledger URL) |
