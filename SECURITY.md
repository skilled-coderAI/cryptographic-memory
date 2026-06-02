# Security Policy

`cryptomem` is a cryptographically verified memory layer for AI agents. Because its
core value is integrity (SHA-256 hashing, Ed25519 signatures, Merkle inclusion
proofs, and an abstain-on-failure grounding gate), we take security reports
seriously and handle them via coordinated disclosure.

## Supported Versions

| Version | Supported |
|---------|-----------|
| `0.1.x` (latest) | ✅ |
| Older / unversioned source builds | ❌ |

We support the latest published release on
[PyPI](https://pypi.org/project/cryptomem/) and
[crates.io](https://crates.io/crates/cryptomem-rs). Please reproduce issues against
the latest version before reporting.

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

- Preferred: open a private [GitHub Security Advisory](https://github.com/skilled-coderAI/cryptographic-memory/security/advisories/new)
  ("Report a vulnerability").
- Alternatively, email **jayakarthi.d@gmail.com** with:
  - a description of the issue and its impact,
  - steps to reproduce (a minimal proof-of-concept is ideal),
  - affected version(s) and environment (OS, Python/Rust, store backend),
  - any suggested remediation.

Please give us a reasonable opportunity to investigate and remediate before any
public disclosure.

## What to Expect

- **Acknowledgement** within 3 business days.
- **Initial assessment** (severity, affected versions) within 7 business days.
- **Fix & coordinated release**: we aim to ship a patched release and publish an
  advisory within 90 days, sooner for actively exploited issues.
- **Credit**: with your permission, we will credit you in the advisory and release
  notes.

## Scope — areas of particular interest

- Signature verification or hash-canonicalization bypass (forging a "verified" node).
- Cross-language signing mismatches between the Python engine and `cryptomem-rs`.
- Merkle inclusion-proof forgery or ledger-root tampering.
- Grounding-gate bypass that causes unverified content to be injected instead of
  abstaining.
- Key handling / BYOK provider weaknesses.
- Authentication/authorization issues on the sidecar (`/cmem/v1/*`) or remote backend.

Thank you for helping keep `cryptomem` and its users safe.
