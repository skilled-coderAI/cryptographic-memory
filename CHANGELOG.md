# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Two artifacts are versioned from this repo: the Python package **`cryptomem`**
and the Rust client crate **`cryptomem-rs`**. Protocol-affecting changes are
marked under a **Protocol** heading and bump both packages together (see
[`docs/packaging_and_release.md`](./docs/packaging_and_release.md) §4).

## [Unreleased]

## [0.1.5] - 2026-06-04

### Added
- Web example **`python/examples/database example/`**: a manus.im-style chat UI where
  you ask a seeded SQLite sales/CRM database plain-English questions and a local Ollama
  model answers strictly from cryptographically verified facts derived from that database
  (no SQL is generated or executed). Includes a live reasoning pipeline panel
  (understand → recall verified DB facts → verify → ground → synthesize), voice input
  (speech-to-text) and spoken answers (text-to-speech), and a `README.md` with run and
  embedder-tuning guidance.

## [0.1.4] - 2026-06-03

### Added
- Runnable [agno](https://github.com/agno-agi/agno) examples grounded in verified memory:
  a minimal quickstart (`python/examples/agno_quickstart.py`) and a polished, manus.im-style
  web view (`python/examples/detailed example/`) that streams the live verified-memory
  pipeline (embed → retrieve → verify → ground → synthesize) over a local Ollama model.

## [0.1.3] - 2026-06-02

### Added
- Top-level `LICENSE-MIT` + `LICENSE-APACHE` text files matching the declared
  `MIT OR Apache-2.0` package metadata.
- `SECURITY.md` with coordinated-disclosure policy, supported versions, and crypto-specific scope.
- Framework integration guides for [agno](https://github.com/agno-agi/agno) (Python),
  [swarms-rs](https://github.com/The-Swarm-Corporation/swarms-rs) (Rust), and
  [`hermes-agent`](https://github.com/NousResearch/hermes-agent) (Nous Research) —
  see [`docs/framework_integrations.md`](./docs/framework_integrations.md) and
  [`docs/hermes_integration.md`](./docs/hermes_integration.md).

### Changed
- Documentation across all markdown now reflects the **published** status with live
  `pip install cryptomem` / `cargo add cryptomem-rs` commands and registry badges.

## [0.1.2] - 2026-06-02

### Fixed
- Packaging and release-workflow hardening for the automated PyPI + crates.io publish.

## [0.1.1] - 2026-06-01

### Changed
- Metadata, classifiers, and dual-license (`MIT OR Apache-2.0`) declaration on both registries.

## [0.1.0] - 2026-06-01

### Added
- First published release. Python engine **`cryptomem`** on
  [PyPI](https://pypi.org/project/cryptomem/) and typed Rust client **`cryptomem-rs`** on
  [crates.io](https://crates.io/crates/cryptomem-rs), with tagged
  [GitHub Releases](https://github.com/skilled-coderAI/cryptographic-memory/releases).
- SHA-256 / Ed25519 signed memory with Merkle inclusion proofs, vector + knowledge-graph
  retrieval, a strict abstain-on-failure grounding gate, accuracy pillars, proactive memory,
  BYOK key providers, and SQLite / Neo4j / remote-backend stores behind an
  Ollama-compatible sidecar.
- Cross-language signing: the Rust client signs nodes that the Python engine verifies byte-for-byte.
- Open-source governance: `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `ROADMAP.md`,
  issue/PR templates, CI and release workflows.

[Unreleased]: https://github.com/skilled-coderAI/cryptographic-memory/compare/v0.1.5...HEAD
[0.1.5]: https://github.com/skilled-coderAI/cryptographic-memory/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/skilled-coderAI/cryptographic-memory/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/skilled-coderAI/cryptographic-memory/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/skilled-coderAI/cryptographic-memory/releases/tag/v0.1.2
[0.1.1]: https://github.com/skilled-coderAI/cryptographic-memory/releases/tag/v0.1.1
[0.1.0]: https://github.com/skilled-coderAI/cryptographic-memory/releases/tag/v0.1.0
