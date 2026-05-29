# Contributing to cryptomem

First off — thank you for considering a contribution! `cryptomem` is an open-source, model-agnostic **cryptographically verified memory plugin** for AI agents. It ships in two parts:

- **`cryptomem`** — the Python engine + Ollama-compatible sidecar (this repo, `python/`).
- **`cryptomem-rs`** — the Rust client SDK over the sidecar REST API (`rust/`).

This guide explains how to set up, develop, test, and submit changes. Please also read our [Code of Conduct](./CODE_OF_CONDUCT.md) and the design docs under [`docs/`](./docs) — especially [`docs/research_overview.md`](./docs/research_overview.md).

---

## 1. Ways to Contribute

- **Code** — implement a roadmap item (see [`ROADMAP.md`](./ROADMAP.md)), fix a bug, add a backend/adapter.
- **Docs** — improve guides, add examples (Hermes, LangGraph, etc.), fix typos.
- **Testing & benchmarks** — expand the integrity / token-budget / grounding test suites, add eval datasets.
- **Triage** — reproduce issues, label, and help newcomers.
- **Ideas** — open a [Discussion](#7-community) or an RFC issue for larger design changes.

> New here? Look for issues labelled **`good first issue`** and **`help wanted`**. Comment to claim one before starting.

---

## 2. Project Layout

```
.
├── python/        # cryptomem (engine + sidecar)  -> PyPI
├── rust/          # cryptomem-rs (client SDK)      -> crates.io
├── docs/          # design & research documents
├── examples/      # runnable integrations (ollama, hermes, ...)
├── ROADMAP.md
├── CODE_OF_CONDUCT.md
└── CONTRIBUTING.md
```

Architecture and module breakdown live in [`docs/implementation_plan.md`](./docs/implementation_plan.md).

---

## 3. Development Setup

### 3.1 Python (`cryptomem`)

Works on a "potato" laptop (8 GB, CPU-only) — see [`docs/low_spec_hardware.md`](./docs/low_spec_hardware.md).

```bash
cd python
python -m venv .venv
.venv\Scripts\activate           # Windows;  source .venv/bin/activate on *nix
pip install -e ".[local,serve,dev]"
```

Run the checks:

```bash
ruff check .            # lint
ruff format --check .   # formatting
mypy cryptomem          # type check
pytest                  # tests (mock mode -> no models/GPU needed)
```

> Most tests use **mock mode** (`adapter="mock"`, stub embedder) so they run with zero model downloads. Only integration tests touch a real Ollama; gate them behind `-m integration` and use the tiny `qwen2.5:0.5b` model.

### 3.2 Rust (`cryptomem-rs`)

```bash
cd rust
cargo build
cargo fmt --all -- --check
cargo clippy --all-targets -- -D warnings
cargo test
```

The Rust crate talks to a running sidecar; start one for integration tests:

```bash
cryptomem serve --port 8088 --ollama-url http://localhost:11434
```

---

## 4. Coding Standards

- **Python**: PEP 8 via **ruff**; type hints required, checked with **mypy**; target `>=3.10`.
- **Rust**: **rustfmt** + **clippy** clean (warnings denied); document public items.
- Keep the **wire format** (`MemoryNode`, `crypto` envelope, `/cmem/v1/*` routes) identical across Python and Rust — it is the contract. Changes require a doc update in [`docs/api_documentation.md`](./docs/api_documentation.md).
- **Security/crypto code** changes must include tests proving tamper rejection (mutated content/signature ⇒ rejected). Never weaken the grounding/verification gate without discussion.
- Add or update tests for any behavior change. No new public API without docs.

---

## 5. Commit & PR Process

1. **Fork** and create a branch: `feat/short-description` or `fix/short-description`.
2. Use **[Conventional Commits](https://www.conventionalcommits.org/)** (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`) — this drives automated changelogs and version bumps.
3. **Sign off** your commits (DCO): `git commit -s`. By signing off you certify the [Developer Certificate of Origin](https://developercertificate.org/).
4. Ensure lint, type checks, and tests pass locally.
5. Open a PR against `main`. Fill in the PR template: what changed, why, and how it was tested. Link the issue (`Closes #123`).
6. A maintainer reviews; address feedback by pushing follow-up commits (don't force-push during review unless asked).
7. PRs are squash-merged with a Conventional-Commit title.

**Large/breaking changes** (new endpoint, schema change, new verification pillar) start as an **RFC issue** referencing the relevant doc in `docs/` before code.

---

## 6. Reporting Bugs & Security Issues

- **Bugs**: open an issue using the bug template; include OS, Python/Rust version, Ollama version & model, and a minimal repro.
- **Security vulnerabilities**: do **not** open a public issue. Email **security@cryptomem.dev** *(replace before release)* with details. We follow coordinated disclosure (see `SECURITY.md` once published).

---

## 7. Community

- **GitHub Discussions** — questions, ideas, show-and-tell.
- **Issues** — actionable bugs and tasks.
- Be kind and assume good intent; all interaction is governed by the [Code of Conduct](./CODE_OF_CONDUCT.md).

Maintainers aim to triage new issues within a few days. If something stalls, a polite ping is welcome.

---

## 8. License

By contributing, you agree that your contributions will be licensed under the project's license (**dual `MIT OR Apache-2.0`**, pending finalization — see [`ROADMAP.md`](./ROADMAP.md) §"Pre-release checklist"). The Apache-2.0 option provides an explicit patent grant, which matters for cryptographic code.
