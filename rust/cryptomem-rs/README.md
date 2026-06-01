# cryptomem-rs

Typed Rust client for the [cryptomem](../../README.md) verified-memory sidecar.

Point any Ollama Rust client (e.g. `ollama-rs`) at the sidecar to get verified
memory transparently. Use this crate when you also want to **read provenance**
or **manage memory** directly — including signing nodes locally so the Python
engine verifies them (zero-trust ingest).

```rust
use cryptomem_rs::{CryptoMemClient, crypto::Signer};
use serde_json::json;

let client = CryptoMemClient::new("http://127.0.0.1:8088")
    .with_signer(Signer::generate());

// Signed in Rust, verified in Python.
let node = client.archive_signed(
    "Project Phoenix",
    "Budget approved at 4.2M for FY26.",
    vec![],
    json!({ "source": "Q3.pdf" }),
)?;
assert_eq!(node.verified, Some(true));

// Ask a question answered only from verified memory.
let answer = client.chat("qwen2.5:0.5b", "What budget did Project Phoenix get?")?;
println!("{}", answer.message.content);
println!("provenance: {}", answer.cryptomem);
```

## Cross-language crypto

`crypto::Signer` reproduces the Python engine's SHA-256 canonical hash and
Ed25519 signature **byte-for-byte** (see `tests/crypto_vectors.rs`), so a
Rust-signed `MemoryNode` passes the server's verification at
`POST /cmem/v1/memory/signed`.

## Use with [swarms-rs](https://github.com/The-Swarm-Corporation/swarms-rs)

Wrap this client in a swarms-rs `Tool` so any agent in a swarm grounds its
answers on signature-verified facts (and abstains otherwise). The agent's LLM
keeps talking to its OpenAI-compatible transport; only memory routes through
cryptomem:

```rust
use cryptomem_rs::CryptoMemClient;
use swarms_rs::structs::tool::{Tool, ToolDyn, ToolError};

struct VerifiedMemoryTool { sidecar_url: String }

impl Tool for VerifiedMemoryTool {
    fn name(&self) -> &str { "memory_search" }
    fn definition(&self) -> swarms_rs::llm::request::ToolDefinition {
        serde_json::json!({
            "name": "memory_search",
            "description": "Return only cryptographically verified facts; abstain if empty.",
            "parameters": { "type": "object",
                "properties": { "query": { "type": "string" } }, "required": ["query"] }
        }).into()
    }
}
// ToolDyn::call parses {"query": ...} and calls CryptoMemClient::query.
```

Full runnable example crate:
[`../examples/swarms-verified-memory`](../examples/swarms-verified-memory).
See also [`../../docs/framework_integrations.md`](../../docs/framework_integrations.md).

## Features

- `http` *(default)* — the blocking `CryptoMemClient` (pulls in `reqwest`).
  Disable with `default-features = false` for a dependency-light build that
  keeps only `models` + `crypto` (signing/verification, no networking).
