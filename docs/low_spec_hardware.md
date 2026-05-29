# Running & Developing `cryptomem` on Low-Spec ("Potato") Hardware

> Research document — part of the pre-development research phase.
> Companions: [`./implementation_plan.md`](./implementation_plan.md), [`./api_documentation.md`](./api_documentation.md), [`./accuracy_and_hallucination.md`](./accuracy_and_hallucination.md).
>
> **Goal:** confirm the plugin can be *developed and run* on a constrained laptop, and specify the exact stack + config that fits, with grounded numbers.

---

## 1. Target Hardware Profile

| Spec | "Potato" (minimum) | Comfortable |
|------|--------------------|-------------|
| RAM | 8 GB | 16 GB |
| CPU | Dual/quad-core x86-64 **with AVX2** | Modern quad-core+ |
| GPU | None (CPU-only) | Optional |
| Disk | ~10 GB free, SSD preferred | SSD |

> **Grounded:** For CPU-only Ollama inference, **8 GB system RAM is the practical minimum** for small models; 16 GB is recommended for multitasking. The CPU should support **AVX2**. ([Ollama hardware guide](https://dev.to/lingdas1/hardware-guide-what-do-you-actually-need-to-run-local-llms-1eik), [Ollama RAM requirements](https://adhdecode.com/articles/ollama/ollama-memory-ram-requirements-model-sizes/))
>
> If you have **4 GB RAM or no AVX2**, do not run Ollama locally — use **Mock mode** for development (§5) and point at a remote Ollama only when needed.

---

## 2. The Key Decision: What NOT to Run Locally

The full architecture (Neo4j + LLMLingua-2 + NLI + semantic entropy + CoVe) will **not** fit comfortably on 8 GB. The low-spec profile drops the heavy pieces and keeps the verifiable core.

| Component (default plan) | Potato-mode decision | Reason (grounded) |
|--------------------------|----------------------|-------------------|
| **Neo4j** graph DB | ❌ Replace with **SQLite + `sqlite-vec`** | Neo4j is a server needing explicit heap + page-cache tuning and significantly more RAM; SQLite is zero-config, in-process, file-based. ([Neo4j memory config](https://neo4j.com/docs/operations-manual/5/performance/memory-configuration/), [SQLite vs Neo4j](https://stackshare.io/stackups/neo4j-vs-sqlite)) |
| **LLMLingua-2** compression | ⚠️ **Off by default**; optional | The model `llmlingua-2-bert-base-multilingual-cased-meetingbank` is **~110M params (BERT-base)** — adds load + CPU latency. ([model card](https://huggingface.co/microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank)) Use heuristic compression instead (§4). |
| **Semantic entropy** (N samples) | ❌ Off by default | Requires N model generations per query — multiplies latency on a CPU. |
| **Chain-of-Verification** | ❌ Off by default | Multi-pass generation; too slow on CPU. |
| **NLI faithfulness** (DeBERTa-base ~440M) | ⚠️ Use a **MiniLM-class NLI**, lazy-loaded, on-demand | Full DeBERTa is heavy; a small cross-encoder NLI keeps RAM down. |

---

## 3. Recommended Potato-Mode Stack

| Layer | Choice | Footprint (grounded) |
|-------|--------|----------------------|
| LLM | **Ollama `qwen2.5:0.5b`** or **`llama3.2:1b`** (Q4) | qwen2.5:0.5b ≈ **0.4–1 GB**; llama3.2:1b ≈ **0.8–2.5 GB** RAM. ([Ollama RAM calc](https://localaimaster.com/blog/ollama-model-ram-vram-table)) |
| Store | **SQLite** + `sqlite-vec` (or `chromadb` local) | ~tens of MB process overhead; file-based. |
| Embeddings | **`all-MiniLM-L6-v2`** (FP16 / ONNX) | **~80–88 MB** (FP32), **~44 MB** FP16; 384-dim, ~22.7M params; CPU latency ~8–150 ms/sentence. ([model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)) |
| Signing | **PyNaCl** Ed25519 | Negligible (C lib). |
| Compression | **Heuristic** (off by default) | No model load. |
| NLI (optional) | small cross-encoder NLI, lazy-loaded | Loaded only when faithfulness checking is enabled. |

### 3.1 RAM Budget Worked Example (8 GB laptop)

| Item | RAM |
|------|-----|
| OS + editor + browser tab | ~3.0 GB |
| Ollama + `qwen2.5:0.5b` (Q4) | ~1.0 GB |
| Python plugin process | ~0.3 GB |
| `all-MiniLM-L6-v2` (FP16, loaded) | ~0.2 GB |
| SQLite + vector index | ~0.2 GB |
| **Headroom** | ~3.3 GB |

→ **Fits.** Adding LLMLingua-2 (~0.5 GB+) or an NLI model (~0.5–1.5 GB) eats the headroom — load them **only on demand**, never resident.

---

## 4. Token Efficiency Without the Heavy Compressor

LLMLingua-2 is the most accurate compressor but the heaviest. On potato hardware, get most of the benefit model-free:

1. **Strict token budget** (`tiktoken` count, hard cap) — already in `efficiency/budgeter.py`.
2. **Deduplication** via the already-loaded MiniLM embeddings (no extra model).
3. **Extractive/heuristic compression** — keep highest-ranked sentences, drop stopword-heavy/low-information spans; preserve structural tokens (`\n . ? !`).
4. **Semantic cache** — biggest CPU win: skip the LLM entirely on repeat queries.

> Expose `CRYPTOMEM_COMPRESSION=heuristic|llmlingua|off`. Default to `heuristic` on potato mode.

---

## 5. Develop Without Burning the Laptop: Mock Mode

Most plugin logic (signing, hashing, store, retrieval ranking, citation binding, API routing) needs **no model at all**. Build and unit-test these with models mocked.

- **Mock LLM adapter** — returns canned/echo responses, so the full pipeline runs with zero model RAM.
- **Stub embedder** — deterministic fixed-dim vectors for reproducible retrieval tests.
- **`respx`** to mock the Ollama HTTP endpoints (already in dev deps).

```python
# tests use a mock adapter -> no Ollama, no models loaded
mem = cryptomem.MemoryClient(mode="sqlite", adapter="mock", embedder="stub")
```

Only spin up real Ollama for **integration tests**, and only with `qwen2.5:0.5b`.

---

## 6. Potato-Mode Configuration

```ini
# .env  (low-spec profile)
CRYPTOMEM_MODE=sqlite
CRYPTOMEM_OLLAMA_URL=http://localhost:11434
CRYPTOMEM_DEFAULT_MODEL=qwen2.5:0.5b
CRYPTOMEM_EMBEDDER=all-MiniLM-L6-v2
CRYPTOMEM_EMBEDDER_BACKEND=onnx          # quantized CPU inference
CRYPTOMEM_COMPRESSION=heuristic          # off | heuristic | llmlingua
CRYPTOMEM_MAX_CONTEXT_TOKENS=1000        # tighter budget on CPU
CRYPTOMEM_REQUIRE_VERIFICATION=true

# Heavy accuracy features OFF by default on potato
CRYPTOMEM_FAITHFULNESS_NLI=false         # lazy-load only if true
CRYPTOMEM_UNCERTAINTY_SAMPLES=1          # disables semantic entropy
CRYPTOMEM_COVE_ENABLED=false

# Resource caps
OLLAMA_NUM_PARALLEL=1                     # serialize requests
OLLAMA_MAX_LOADED_MODELS=1
OMP_NUM_THREADS=4                         # cap CPU threads for torch/onnx
```

### Tiered profiles
- **`potato`**: above — SQLite, tiny model, heuristic compression, verification core only.
- **`standard`** (16 GB+): enable LLMLingua-2, optional NLI faithfulness.
- **`server`**: Neo4j + full verification pipeline (not for laptops).

---

## 7. Practical CPU Tips (Grounded)

- Confirm **AVX2** support; without it Ollama performance degrades badly. ([requirements](https://llmhardware.io/guides/llm-system-requirements))
- Use **Q4_K_M** quantized models — ~1 GB RAM per 1B params at 8-bit, less at 4-bit. ([RAM rule](https://adhdecode.com/articles/ollama/ollama-memory-ram-requirements-model-sizes/))
- Keep **one model loaded** (`OLLAMA_MAX_LOADED_MODELS=1`) and **serialize** requests.
- Prefer **ONNX + quantized** embeddings/NLI over PyTorch to cut RAM and startup time. `all-MiniLM-L6-v2` ships ONNX/TFLite variants. ([model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2))
- **Lazy-load** any optional transformer (NLI/compressor); unload after use; never keep resident.
- Cap thread counts (`OMP_NUM_THREADS`) so background model work doesn't freeze your editor.

---

## 8. Feature Availability by Profile

| Feature | potato (8 GB) | standard (16 GB) | server |
|---------|:---:|:---:|:---:|
| Ed25519 signing + verification | ✅ | ✅ | ✅ |
| SQLite relational store | ✅ | ✅ | optional |
| Neo4j graph store | ❌ | optional | ✅ |
| MiniLM embeddings retrieval | ✅ | ✅ | ✅ |
| Heuristic compression | ✅ | ✅ | ✅ |
| LLMLingua-2 compression | ❌ (on-demand only) | ✅ | ✅ |
| NLI faithfulness | on-demand | ✅ | ✅ |
| Semantic entropy / CoVe | ❌ | optional | ✅ |
| Mock-mode development | ✅ | ✅ | ✅ |

> **Accuracy impact:** on potato mode you keep the strongest, cheapest lever — **strict grounding + signature verification + abstention** (see `./accuracy_and_hallucination.md` §2.1). The expensive faithfulness/uncertainty passes are what you trade away; enable them later on better hardware or selectively on-demand.

---

## 9. Verified References

- **Ollama RAM / CPU (AVX2) requirements:** [ADHDecode RAM guide](https://adhdecode.com/articles/ollama/ollama-memory-ram-requirements-model-sizes/) · [Hardware guide for local LLMs](https://dev.to/lingdas1/hardware-guide-what-do-you-actually-need-to-run-local-llms-1eik) · [Ollama RAM/VRAM table](https://localaimaster.com/blog/ollama-model-ram-vram-table)
- **all-MiniLM-L6-v2 size & CPU latency:** [Hugging Face model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- **Neo4j memory tuning vs SQLite:** [Neo4j memory configuration](https://neo4j.com/docs/operations-manual/5/performance/memory-configuration/) · [SQLite vs Neo4j](https://stackshare.io/stackups/neo4j-vs-sqlite)
- **LLMLingua-2 model size (~110M, BERT-base):** [microsoft/llmlingua-2 model card](https://huggingface.co/microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank)
