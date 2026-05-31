# Packaging & Release Plan (Python + Rust)

> Research document — part of the pre-development research phase.
> Companions: [`../ROADMAP.md`](../ROADMAP.md), [`../CONTRIBUTING.md`](../CONTRIBUTING.md), [`./implementation_plan.md`](./implementation_plan.md).
>
> Goal: a repeatable, secure, automated release of two artifacts — the Python engine/sidecar (`cryptomem` → PyPI) and the Rust client SDK (`cryptomem-rs` → crates.io).

---

## 1. Repository Layout (Monorepo)

```
.
├── python/
│   ├── pyproject.toml          # cryptomem  (engine + sidecar)
│   ├── cryptomem/
│   └── tests/
├── rust/
│   ├── Cargo.toml              # workspace
│   └── crates/
│       └── cryptomem-rs/       # client SDK over the sidecar REST API
├── examples/                   # ollama/, hermes/, langgraph/
├── .github/workflows/          # ci.yml, release-python.yml, release-rust.yml
├── CHANGELOG.md
└── ROADMAP.md
```

A monorepo keeps the **wire protocol** (`MemoryNode`, `/cmem/v1/*`) in one place and lets cross-language integration tests run in one CI.

---

## 2. Python Package — `cryptomem` → PyPI

### 2.1 Build backend
Use **Hatchling** (modern, standards-based). ([Python packaging guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/))

```toml
# python/pyproject.toml
[build-system]
requires = ["hatchling>=1.26"]
build-backend = "hatchling.build"

[project]
name = "cryptomem"
version = "0.1.0"
description = "Cryptographically verified, relational, persistent memory for AI agents."
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT OR Apache-2.0" }
authors = [{ name = "cryptomem contributors" }]
keywords = ["ai", "memory", "cryptography", "graphrag", "ollama", "agents"]
dependencies = [
  "pynacl>=1.5", "pydantic>=2.6", "pydantic-settings>=2.2", "httpx>=0.27",
]

[project.optional-dependencies]
local   = ["sentence-transformers>=3.0", "onnxruntime>=1.17"]
serve   = ["fastapi>=0.110", "uvicorn>=0.29", "tiktoken>=0.7"]
neo4j   = ["neo4j>=5.14"]
dev     = ["pytest>=8", "respx>=0.21", "ruff>=0.6", "mypy>=1.10", "build>=1.2"]

[project.scripts]
cryptomem = "cryptomem.cli:main"     # `cryptomem serve`

[project.urls]
Homepage = "https://github.com/skilled-coderAI/cryptographic-memory"
Documentation = "https://github.com/skilled-coderAI/cryptographic-memory/tree/main/docs"
Issues = "https://github.com/skilled-coderAI/cryptographic-memory/issues"
```

Notes:
- **Pure-Python wheel** (the sidecar is FastAPI; heavy ML deps are *optional extras*), so we publish a single `py3-none-any` wheel + sdist — **no per-OS build matrix** initially.
- Heavy models (NLI, LLMLingua-2) are **never hard dependencies** — they live behind extras so a potato install stays small (see [`./low_spec_hardware.md`](./low_spec_hardware.md)).

### 2.2 Publish via Trusted Publishing (OIDC) — no API tokens
Register a trusted publisher in the PyPI project settings (repo + workflow filename), then: ([PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/))

```yaml
# .github/workflows/release-python.yml
name: release-python
on:
  push:
    tags: ["py-v*"]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install build
      - run: python -m build python/
      - uses: actions/upload-artifact@v4
        with: { name: dist, path: python/dist/* }
  publish:
    needs: build
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write          # OIDC -> short-lived PyPI credential
    steps:
      - uses: actions/download-artifact@v4
        with: { name: dist, path: dist }
      - uses: pypa/gh-action-pypi-publish@release/v1
```

Validate on **TestPyPI** first (same action with `repository-url`), then promote.

The shipped [`release-python.yml`](../.github/workflows/release-python.yml) adds three
guarantees around this skeleton:
- a **`verify-version`** gate that fails the release unless the `py-vX.Y.Z` tag equals both
  `pyproject.toml`'s `version` and `cryptomem.__version__`;
- a **`twine check`** metadata smoke before upload;
- a **`github-release`** job that creates the GitHub Release (auto-generated notes) and
  attaches the built wheel + sdist.
The whole workflow runs under a non-cancelling `concurrency` group so a re-pushed tag can
never race an in-flight publish.

---

## 3. Rust Crate — `cryptomem-rs` → crates.io

`cryptomem-rs` is a **typed client** over the sidecar REST API (`/api/*` + `/cmem/v1/*`).
It also reproduces the canonical hashing + Ed25519 signing **byte-for-byte**, so a
Rust-signed node verifies on the Python engine via `POST /cmem/v1/memory/signed`. The
networking layer is gated behind the default `http` feature, so the crypto core builds
with `--no-default-features` (no `reqwest`/TLS).

```toml
# rust/cryptomem-rs/Cargo.toml
[package]
name = "cryptomem-rs"
version = "0.1.0"
edition = "2021"
rust-version = "1.70"               # documented MSRV
description = "Typed Rust client for the cryptomem verified-memory sidecar, with client-side Ed25519 signing that the Python engine verifies."
license = "MIT OR Apache-2.0"
repository = "https://github.com/skilled-coderAI/cryptographic-memory"
keywords = ["ai", "memory", "cryptography", "ed25519", "rag"]
categories = ["api-bindings", "cryptography"]

[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
sha2 = "0.10"
ed25519-dalek = { version = "2", features = ["rand_core"] }
rand = "0.8"
hex = "0.4"
thiserror = "1"
reqwest = { version = "0.12", default-features = false, features = [
    "blocking", "json", "rustls-tls",
], optional = true }

[features]
default = ["http"]
http = ["dep:reqwest"]
```

### 3.1 Release automation with `release-plz`
Use **release-plz** to derive versions from Conventional Commits, update changelogs, tag, and `cargo publish` workspace members. ([release-plz](https://github.com/release-plz/release-plz/))

```yaml
# .github/workflows/release-rust.yml
name: release-rust
on:
  push:
    branches: [main]
jobs:
  release-plz:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: dtolnay/rust-toolchain@stable
      - uses: release-plz/action@v0
        env:
          CARGO_REGISTRY_TOKEN: ${{ secrets.CARGO_REGISTRY_TOKEN }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

CI always runs a **dry run** before publish: ([Cargo publishing](https://doc.rust-lang.org/cargo/reference/publishing.html))

```bash
cargo publish --dry-run -p cryptomem-rs
```

Required metadata (`description`, `license`, `repository`) must be present or `cargo publish` fails. Use **`cargo yank`** for bad releases (immutable record; keeps lockfiles stable) rather than deletion.

---

## 4. Shared Version Policy

- **SemVer** for both packages. Pre-1.0, minor bumps may break.
- The **wire protocol** is the contract. When a protocol change lands:
  - bump **both** `cryptomem` and `cryptomem-rs` minors together,
  - record it in `CHANGELOG.md` under a "Protocol" heading,
  - add a compatibility note (which sidecar versions a given `cryptomem-rs` speaks to).
- Tags are namespaced: `py-v0.3.0` (Python release workflow), Rust handled by release-plz tags. This avoids cross-triggering workflows.
- `CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/).

---

## 5. CI Matrix (Quality Gates Before Any Release)

```yaml
# .github/workflows/ci.yml  (sketch)
on: [push, pull_request]
jobs:
  python:
    strategy: { matrix: { py: ["3.10", "3.11", "3.12"] } }
    steps:
      - run: pip install -e "python/.[local,serve,dev]"
      - run: ruff check python/ && ruff format --check python/
      - run: mypy python/cryptomem
      - run: pytest python/ -m "not integration"
      - run: python -m build python/        # wheel/sdist smoke
  rust:
    steps:
      - run: cargo fmt --all -- --check
      - run: cargo clippy --all-targets -- -D warnings
      - run: cargo test --workspace
      - run: cargo publish --dry-run -p cryptomem-rs
```

Integration tests (real Ollama + `qwen2.5:0.5b`) run in a separate, optionally-nightly job so PR CI stays fast and potato-friendly.

---

## 6. Release Checklist (per version)

1. All CI green; changelog updated; docs reflect any API change.
2. Bump version (release-plz for Rust; `hatch version` / tag for Python).
3. Tag: `py-vX.Y.Z` for Python; let release-plz tag Rust.
4. Workflows publish to PyPI (OIDC) and crates.io (token), create a GitHub Release with notes.
5. Verify installs from a clean machine: `pip install cryptomem[local,serve]` and `cargo add cryptomem-rs`.
6. Announce per the community plan in [`../ROADMAP.md`](../ROADMAP.md).

---

## 7. Verified References

- **Python packaging / pyproject:** [packaging.python.org](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
- **PyPI Trusted Publishing (OIDC):** [docs.pypi.org/trusted-publishers](https://docs.pypi.org/trusted-publishers/) · [pypa/gh-action-pypi-publish]
- **Cargo publishing & yank:** [The Cargo Book — Publishing](https://doc.rust-lang.org/cargo/reference/publishing.html)
- **release-plz:** [github.com/release-plz/release-plz](https://github.com/release-plz/release-plz/)
- **Keep a Changelog:** [keepachangelog.com](https://keepachangelog.com/)
- **SemVer:** [semver.org](https://semver.org/)
