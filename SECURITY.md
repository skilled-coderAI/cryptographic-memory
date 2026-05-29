# Security Policy

`cryptomem` is security-sensitive software: it provides **cryptographic verification** of AI memory. We take vulnerabilities seriously and appreciate responsible disclosure.

## Supported Versions

Until `1.0.0`, only the **latest** released minor version receives security fixes.

| Version | Supported |
|---------|-----------|
| latest `0.x` | ✅ |
| older `0.x` | ❌ |

## Reporting a Vulnerability

**Do not open a public issue, PR, or Discussion for security vulnerabilities.**

Please report privately via one of:

1. **GitHub Security Advisories** — use the repository's *Security → Report a vulnerability* (preferred; enables coordinated disclosure).
2. **Email** — **security@cryptomem.dev** *(replace with the project's real address before release)*. Encrypt with our PGP key if handling sensitive details.

Please include:

- A description of the issue and its impact.
- Steps to reproduce (PoC if possible).
- Affected version(s), OS, Python/Rust, and Ollama version/model.
- Any suggested remediation.

## What to Expect

- **Acknowledgement** within **3 business days**.
- An initial assessment and severity rating within **7 business days**.
- Coordinated disclosure: we agree on a timeline (typically ≤ 90 days) and credit you in the advisory unless you prefer to remain anonymous.

## Scope — Examples of In-Scope Issues

- Bypassing signature/hash verification (serving tampered memory as verified).
- Forging Merkle inclusion proofs.
- Key handling / BYOK flaws that expose private keys.
- Auth bypass on the sidecar API.
- Injection that causes unverified content to be treated as grounded.

## Out of Scope

- Vulnerabilities in upstream dependencies (report to them; we will bump once fixed).
- Hallucinations of the underlying LLM on content **not** stored in verified memory — by design, `cryptomem` only guarantees grounded/verified facts and abstains otherwise (see [`docs/accuracy_and_hallucination.md`](./docs/accuracy_and_hallucination.md)).
- Issues requiring a compromised host / physical access.

Thank you for helping keep `cryptomem` and its users safe.
