# Repository Guidelines

This repository hosts `cryptomem`, a cryptographically verified, relational, persistent memory engine for AI agents. The Python engine (`python/`) is implemented through Phase P5: signed/hashed memory nodes with Merkle anchoring and verifiable inclusion proofs, vector + knowledge-graph retrieval, a strict grounding gate, token-budget/dedupe/compress efficiency, an Ollama-compatible FastAPI sidecar, accuracy pillars (faithfulness, citations, semantic-entropy confidence, Chain-of-Verification), proactive memory (planner / triggers / write-back), BYOK key providers, and pluggable stores (`SqliteStore`, `Neo4jStore`, `RemoteStore`) selected by `CRYPTOMEM_MODE`. The `rust/` SDK is not yet implemented.

## Project Structure & Module Organization

This is a monorepo partitioned by language:
- `python/`: Contains the `cryptomem` engine and Ollama-compatible sidecar.
- `rust/`: Contains `cryptomem-rs`, the Rust client SDK connecting to the sidecar.
- `docs/`: Holds architectural blueprints, research logic, and API documentation. The design contract between Python and Rust relies on the wire format (`MemoryNode` and `/cmem/v1/*` routes) documented here.

## Build, Test, and Development Commands

### Python (`python/`)
- **Install**: `pip install -e ".[local,serve,dev]"` (add `neo4j` for the graph store).
- **Run Sidecar**: `cryptomem serve --port 8088 --ollama-url http://localhost:11434`
- **Unit Tests**: `pytest python/ -m "not integration"`
- **Integration Tests**: `pytest -m integration`
- **Build Package**: `python -m build python/`

### Rust (`rust/`)
- **Build**: `cargo build --manifest-path rust/Cargo.toml`
- **Test**: `cargo test --manifest-path rust/Cargo.toml --workspace`

## Coding Style & Naming Conventions

- **Python**: Enforce PEP 8 style using `ruff`. Require type hints, targeting Python `>=3.10`.
  - Format: `ruff format --check python/`
  - Lint: `ruff check python/`
  - Type Check: `mypy python/cryptomem`
- **Rust**: Ensure code is free of warnings and formatted correctly. Public items must be documented.
  - Format: `cargo fmt --all --manifest-path rust/Cargo.toml -- --check`
  - Lint: `cargo clippy --manifest-path rust/Cargo.toml --all-targets -- -D warnings`

## Testing Guidelines

- Python primarily uses `pytest` in **mock mode** (stub embedder, `adapter="mock"`) to avoid model downloads.
- Integration tests interact with a local Ollama instance (typically using `qwen2.5:0.5b`).
- Any changes to security or cryptographic code must include dedicated tests demonstrating **tamper rejection** (mutated content or signatures must be explicitly rejected).

## Commit & Pull Request Guidelines

- Commits must adhere to **Conventional Commits** (e.g., `feat:`, `fix:`, `docs:`, `chore(deps):`).
- Every commit must include a Developer Certificate of Origin sign-off (`git commit -s`).
- PRs must complete the provided checklist, including lint, type check, and test verification.
- Significant breaking changes or wire protocol modifications must begin with an RFC issue referencing the relevant `docs/` architecture blueprint.