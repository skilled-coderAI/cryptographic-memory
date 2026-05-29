<!-- Thanks for contributing to cryptomem! Please read CONTRIBUTING.md first. -->

## What & Why

<!-- What does this PR change, and why? Link the issue. -->
Closes #

## Type of change

- [ ] `fix` — bug fix (non-breaking)
- [ ] `feat` — new feature (non-breaking)
- [ ] `docs` — documentation only
- [ ] `refactor` / `chore` / `test`
- [ ] **Breaking change** (API or wire protocol)
- [ ] **Protocol change** (affects `MemoryNode` / `/cmem/v1/*` — requires bumping both `cryptomem` and `cryptomem-rs`)

## How was it tested?

<!-- Commands run, OS, Python/Rust version, Ollama version & model if relevant. -->

## Checklist

- [ ] Commits use [Conventional Commits](https://www.conventionalcommits.org/) and are signed off (`git commit -s`, DCO).
- [ ] Lint/format pass (`ruff` / `cargo fmt` + `clippy`).
- [ ] Type checks pass (`mypy`).
- [ ] Tests added/updated and passing (`pytest` / `cargo test`).
- [ ] For crypto/verification changes: added a test proving **tamper rejection**.
- [ ] Docs updated (especially `docs/api_documentation.md` if the wire format changed).
- [ ] `CHANGELOG.md` updated under `[Unreleased]` if user-facing.
