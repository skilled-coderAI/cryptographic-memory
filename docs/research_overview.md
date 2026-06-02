# Cryptographic Memory Plugin — Research Overview

> **Status:** Design & reference docs for the **published** `cryptomem` plugin —
> [`cryptomem` on PyPI](https://pypi.org/project/cryptomem/) (`pip install cryptomem`) and
> [`cryptomem-rs` on crates.io](https://crates.io/crates/cryptomem-rs) (`cargo add cryptomem-rs`).
> These documents capture the architecture, grounding, and feasibility analysis behind the implementation.

## Problem Statement
AI agents depend on large models because small/local models hallucinate and lack persistent, verifiable memory. `cryptomem` is a model-agnostic plugin that gives any model (including local Ollama SLMs) a relational, persistent, **cryptographically verified** memory — improving accuracy, enabling proactiveness, and reducing token consumption.

## Document Map

| Document | Purpose | Audience |
|----------|---------|----------|
| [`./cryptographic_memory.md`](./cryptographic_memory.md) | Architecture & concepts: cryptographic verification, relational/GraphRAG persistence, premium features. | Vision / stakeholders |
| [`./implementation_plan.md`](./implementation_plan.md) | Engineering blueprint: package structure, modules, token-efficiency & proactiveness design, roadmap, dependencies. | Engineers |
| [`./api_documentation.md`](./api_documentation.md) | Public API: Ollama-compatible sidecar + native REST, Python SDK, Rust integration. | Integrators (Python & Rust) |
| [`./accuracy_and_hallucination.md`](./accuracy_and_hallucination.md) | How to reach ~90% hallucination reduction / >95% grounded accuracy; verification pipeline & eval harness. | Engineers / research |
| [`./low_spec_hardware.md`](./low_spec_hardware.md) | Running & developing on a low-spec ("potato") laptop: fitting stack, RAM budget, mock-mode dev, tiered profiles. | Engineers |
| [`./hermes_integration.md`](./hermes_integration.md) | Grounded plan for integrating with the NousResearch Hermes agent (sidecar + tool-calling modes). | Engineers / community |
| [`./packaging_and_release.md`](./packaging_and_release.md) | Packaging & release strategy: Python→PyPI (Hatchling/OIDC), Rust→crates.io (release-plz), CI, versioning. | Maintainers |
| [`../README.md`](../README.md) · [`../ROADMAP.md`](../ROADMAP.md) · [`../CONTRIBUTING.md`](../CONTRIBUTING.md) · [`../CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) · [`../SECURITY.md`](../SECURITY.md) · [`../CHANGELOG.md`](../CHANGELOG.md) | Open-source governance & GitHub scaffolding: front-page, release train, how to contribute, community standards, vulnerability disclosure, changelog. | Everyone |

## Core Design Decisions (so far)

1. **Cryptographic provenance** — every memory node is hashed (SHA-256) and signed (Ed25519/PyNaCl); unverified or tampered facts are never injected.
2. **Relational persistence** — GraphRAG-style nodes + edges via `neo4j-graphrag`, with a local SQLite/Chroma fallback for edge devices.
3. **Cross-language via Ollama-compatible sidecar** — the Python engine is exposed over HTTP using Ollama's own wire protocol, so Rust (`ollama-rs`) and Python (`ollama`) clients work by only changing the base URL.
4. **Accuracy via grounding + verification + abstention** — strict grounding gate, NLI faithfulness checks, semantic-entropy uncertainty, Chain-of-Verification, and enforced citations; the system abstains rather than guesses.
5. **Token efficiency** — retrieve → dedupe → rank → budget → compress (LLMLingua-2) → semantic cache.

## Open Questions for Active Development
- Default benchmark dataset and domain for measuring the 90/95 targets.
- Which local NLI / reranker / embedding models to standardize on.
- Latency budget for selective semantic-entropy and CoVe passes.
- Acceptable answer (coverage) rate vs. accuracy trade-off.
- Multi-tenant key management and BYOK provider priority (AWS KMS vs. Vault).

## Grounding Summary
All major claims are cross-referenced to verified sources (PyNaCl, neo4j-graphrag, Ollama API, LLMLingua-2, *Nature* 2024 semantic entropy, ACL 2024 CoVe, RAGAS, 2025 RAG grounding/abstention research). Per-document reference lists appear at the end of each file.
