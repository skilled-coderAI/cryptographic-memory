//! Verified memory for a swarms-rs agent.
//!
//! Gives a [swarms-rs](https://github.com/The-Swarm-Corporation/swarms-rs) agent
//! cryptographically verified memory via a custom `Tool`. The agent's LLM talks to
//! Ollama's OpenAI-compatible API directly, while the `VerifiedMemoryTool` routes
//! all factual recall through the cryptomem sidecar with the typed `cryptomem-rs`
//! client -- returning only signature-verified facts, so the agent abstains rather
//! than hallucinates.
//!
//! Run it:
//! ```bash
//! ollama pull qwen2.5:0.5b && ollama serve
//! cryptomem serve --port 8088 --ollama-url http://localhost:11434
//! cd rust/examples/swarms-verified-memory && cargo run
//! ```
//!
//! The tool reads `CRYPTOMEM_SIDECAR_URL` (default `http://127.0.0.1:8088`) and the
//! model reads `OLLAMA_URL` (default `http://localhost:11434/v1`), so the same agent
//! works in dev and prod by changing only the backend URL.

use std::future::Future;
use std::pin::Pin;

use cryptomem_rs::CryptoMemClient;
use swarms_rs::llm::provider::openai::OpenAI;
use swarms_rs::structs::tool::{Tool, ToolDyn, ToolError};

/// A swarms-rs tool that returns only cryptographically verified facts.
struct VerifiedMemoryTool {
    sidecar_url: String,
}

impl VerifiedMemoryTool {
    fn from_env() -> Self {
        Self {
            sidecar_url: std::env::var("CRYPTOMEM_SIDECAR_URL")
                .unwrap_or_else(|_| "http://127.0.0.1:8088".to_string()),
        }
    }
}

impl Tool for VerifiedMemoryTool {
    fn name(&self) -> &str {
        "memory_search"
    }

    fn definition(&self) -> swarms_rs::llm::request::ToolDefinition {
        serde_json::json!({
            "name": "memory_search",
            "description": "Retrieve cryptographically verified facts relevant to a \
                            query. Returns ONLY signature-verified memory nodes; if \
                            the result is empty you must abstain instead of guessing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": { "type": "string", "description": "What to recall" }
                },
                "required": ["query"]
            }
        })
        .into()
    }
}

impl ToolDyn for VerifiedMemoryTool {
    fn call(
        &self,
        args: String,
    ) -> Pin<Box<dyn Future<Output = Result<String, ToolError>> + Send + '_>> {
        let sidecar_url = self.sidecar_url.clone();
        Box::pin(async move {
            let query = serde_json::from_str::<serde_json::Value>(&args)
                .ok()
                .and_then(|v| v.get("query").and_then(|q| q.as_str()).map(str::to_owned))
                .unwrap_or_default();

            // CryptoMemClient is blocking; keep the async runtime free. Any failure
            // is returned to the model as readable text rather than aborting the run.
            let formatted = tokio::task::spawn_blocking(move || {
                let client = CryptoMemClient::new(sidecar_url);
                let result = match client.query(&query, 5, 0) {
                    Ok(result) => result,
                    Err(e) => return format!("MEMORY_BACKEND_ERROR: {e}"),
                };

                let verified: Vec<String> = result
                    .nodes
                    .iter()
                    .filter(|n| n.verified != Some(false))
                    .map(|n| format!("- [{}] ({}) {}", n.node_id, n.entity, n.content))
                    .collect();

                if verified.is_empty() {
                    "NO_VERIFIED_MEMORY: abstain; do not guess.".to_string()
                } else {
                    format!("VERIFIED_FACTS:\n{}", verified.join("\n"))
                }
            })
            .await
            .unwrap_or_else(|e| format!("MEMORY_TASK_ERROR: {e}"));

            Ok(formatted)
        })
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let ollama_url =
        std::env::var("OLLAMA_URL").unwrap_or_else(|_| "http://localhost:11434/v1".to_string());
    let model = std::env::var("OLLAMA_MODEL").unwrap_or_else(|_| "qwen2.5:0.5b".to_string());

    // The LLM transport stays OpenAI-compatible (Ollama); memory goes through cryptomem.
    let client = OpenAI::from_url(ollama_url, "ollama").set_model(&model);
    let agent = client
        .agent_builder()
        .agent_name("VerifiedMemoryAgent")
        .system_prompt(
            "You answer strictly from cryptographically verified memory. Always call \
             memory_search before answering a factual question, answer ONLY from the \
             VERIFIED_FACTS it returns, and cite node ids in square brackets. If it \
             returns NO_VERIFIED_MEMORY, say you cannot answer. Never guess.",
        )
        .add_tool(VerifiedMemoryTool::from_env())
        .max_loops(2)
        .build();

    // Grounded if the fact was archived; abstains otherwise.
    let answer = agent
        .run("What budget did Project Phoenix get?".to_owned())
        .await?;
    println!("{answer}");

    Ok(())
}
