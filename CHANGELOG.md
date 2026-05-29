# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Two artifacts are versioned from this repo: the Python package **`cryptomem`**
and the Rust client crate **`cryptomem-rs`**. Protocol-affecting changes are
marked under a **Protocol** heading and bump both packages together (see
[`docs/packaging_and_release.md`](./docs/packaging_and_release.md) §4).

## [Unreleased]

### Added
- Initial research & design documentation under `docs/` (architecture, implementation plan,
  API, accuracy/hallucination strategy, low-spec hardware guide, Hermes integration,
  packaging & release plan).
- Open-source governance: `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `ROADMAP.md`,
  `SECURITY.md`, issue/PR templates, CI and release workflows.

### Notes
- Project is in the **pre-development research phase**. No published packages yet.
- First tagged release will be **`v0.1.0`** (Foundations) — see [`ROADMAP.md`](./ROADMAP.md).

[Unreleased]: https://github.com/skilled-coderAI/cryptographic-memory/commits/main
