//! Blocking HTTP client over the sidecar's `/api/*` and `/cmem/v1/*` routes.

use reqwest::blocking::{Client as HttpClient, RequestBuilder, Response};
use reqwest::StatusCode;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::crypto::Signer;
use crate::error::Error;
use crate::models::{to_metadata, MemoryNode, Relationship};

/// Result of a `/cmem/v1/query` call.
#[derive(Debug, Deserialize)]
pub struct QueryResult {
    #[serde(default)]
    pub nodes: Vec<MemoryNode>,
    #[serde(default)]
    pub verified_count: u32,
    #[serde(default)]
    pub confidences: Vec<f64>,
}

/// Assistant reply plus the sidecar's `cryptomem` provenance block.
#[derive(Debug, Deserialize)]
pub struct ChatResult {
    pub message: ChatMessageBody,
    #[serde(default)]
    pub cryptomem: Value,
}

#[derive(Debug, Deserialize)]
pub struct ChatMessageBody {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Deserialize)]
struct NodeList {
    #[serde(default)]
    nodes: Vec<MemoryNode>,
}

/// A thin, typed client for a running cryptomem sidecar.
pub struct CryptoMemClient {
    base_url: String,
    http: HttpClient,
    api_key: Option<String>,
    signer: Option<Signer>,
}

impl CryptoMemClient {
    /// Create a client pointed at a sidecar base URL (e.g. `http://127.0.0.1:8088`).
    pub fn new(base_url: impl Into<String>) -> Self {
        Self {
            base_url: base_url.into().trim_end_matches('/').to_string(),
            http: HttpClient::new(),
            api_key: None,
            signer: None,
        }
    }

    /// Attach a bearer token sent on every request.
    pub fn with_api_key(mut self, key: impl Into<String>) -> Self {
        self.api_key = Some(key.into());
        self
    }

    /// Attach a signer enabling [`archive_signed`](Self::archive_signed).
    pub fn with_signer(mut self, signer: Signer) -> Self {
        self.signer = Some(signer);
        self
    }

    fn url(&self, path: &str) -> String {
        format!("{}{}", self.base_url, path)
    }

    fn auth(&self, rb: RequestBuilder) -> RequestBuilder {
        match &self.api_key {
            Some(key) => rb.bearer_auth(key),
            None => rb,
        }
    }

    fn handle<T: for<'de> Deserialize<'de>>(&self, resp: Response) -> Result<T, Error> {
        let status = resp.status();
        if status.is_success() {
            Ok(resp.json::<T>()?)
        } else {
            Err(Error::Api {
                status: status.as_u16(),
                body: resp.text().unwrap_or_default(),
            })
        }
    }

    /// `GET /healthz` — `true` if the sidecar answers successfully.
    pub fn healthz(&self) -> Result<bool, Error> {
        let resp = self.auth(self.http.get(self.url("/healthz"))).send()?;
        Ok(resp.status().is_success())
    }

    /// `POST /cmem/v1/memory` — the sidecar signs *and* embeds the node
    /// server-side, so it is immediately vector-searchable.
    pub fn archive(
        &self,
        entity: &str,
        content: &str,
        relationships: Vec<Relationship>,
        metadata: Value,
    ) -> Result<MemoryNode, Error> {
        let body = json!({
            "entity": entity,
            "content": content,
            "relationships": relationships,
            "metadata": metadata,
        });
        let resp = self
            .auth(self.http.post(self.url("/cmem/v1/memory")).json(&body))
            .send()?;
        self.handle(resp)
    }

    /// `POST /cmem/v1/memory/signed` — sign locally (zero-trust) and submit the
    /// already-verifiable node. Requires a signer; the node carries no embedding,
    /// so it is retrievable by id/graph but not by vector query.
    pub fn archive_signed(
        &self,
        entity: &str,
        content: &str,
        relationships: Vec<Relationship>,
        metadata: Value,
    ) -> Result<MemoryNode, Error> {
        let signer = self.signer.as_ref().ok_or_else(|| {
            Error::Crypto("archive_signed requires a signer (use with_signer)".into())
        })?;
        let mut node = MemoryNode::new(
            format!("mem_{}", short_id()),
            entity,
            content,
            relationships,
            to_metadata(metadata),
        );
        signer.seal(&mut node);
        let resp = self
            .auth(
                self.http
                    .post(self.url("/cmem/v1/memory/signed"))
                    .json(&node),
            )
            .send()?;
        self.handle(resp)
    }

    /// `GET /cmem/v1/memory/{id}` — fetch a node, or `None` if it is unknown.
    pub fn get(&self, node_id: &str) -> Result<Option<MemoryNode>, Error> {
        let resp = self
            .auth(
                self.http
                    .get(self.url(&format!("/cmem/v1/memory/{node_id}"))),
            )
            .send()?;
        if resp.status() == StatusCode::NOT_FOUND {
            return Ok(None);
        }
        Ok(Some(self.handle(resp)?))
    }

    /// `POST /cmem/v1/query` — vector + entity retrieval of verified nodes.
    pub fn query(&self, text: &str, top_k: u32, depth: u32) -> Result<QueryResult, Error> {
        let body = json!({ "text": text, "top_k": top_k, "depth": depth });
        let resp = self
            .auth(self.http.post(self.url("/cmem/v1/query")).json(&body))
            .send()?;
        self.handle(resp)
    }

    /// `GET /cmem/v1/memory/{id}/neighbors` — graph traversal of relationships.
    pub fn neighbors(&self, node_id: &str, depth: u32) -> Result<Vec<MemoryNode>, Error> {
        let resp = self
            .auth(
                self.http
                    .get(self.url(&format!("/cmem/v1/memory/{node_id}/neighbors")))
                    .query(&[("depth", depth)]),
            )
            .send()?;
        Ok(self.handle::<NodeList>(resp)?.nodes)
    }

    /// `GET /cmem/v1/ledger/proof/{id}` — Merkle inclusion proof for auditing.
    pub fn proof(&self, node_id: &str) -> Result<Value, Error> {
        let resp = self
            .auth(
                self.http
                    .get(self.url(&format!("/cmem/v1/ledger/proof/{node_id}"))),
            )
            .send()?;
        self.handle(resp)
    }

    /// `POST /api/chat` — Ollama-compatible chat answered from verified memory,
    /// returning the reply plus the `cryptomem` provenance block.
    pub fn chat(&self, model: &str, user_message: &str) -> Result<ChatResult, Error> {
        let body = json!({
            "model": model,
            "stream": false,
            "messages": [{ "role": "user", "content": user_message }],
        });
        let resp = self
            .auth(self.http.post(self.url("/api/chat")).json(&body))
            .send()?;
        self.handle(resp)
    }
}

fn short_id() -> String {
    use rand::RngCore;
    let mut bytes = [0u8; 6];
    rand::rngs::OsRng.fill_bytes(&mut bytes);
    hex::encode(bytes)
}
