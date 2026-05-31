//! Wire types mirroring the Python `MemoryNode` and its crypto envelope.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

/// A typed, directed edge from one memory node to another.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Relationship {
    /// Edge type. Serialized as `"type"` to match the wire protocol.
    #[serde(rename = "type")]
    pub rel_type: String,
    pub target_id: String,
}

impl Relationship {
    pub fn new(rel_type: impl Into<String>, target_id: impl Into<String>) -> Self {
        Self {
            rel_type: rel_type.into(),
            target_id: target_id.into(),
        }
    }
}

/// Integrity metadata bound to a node at write time.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CryptoEnvelope {
    pub hash: String,
    pub signature: String,
    pub public_key_ref: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub merkle_root: Option<String>,
}

/// A single relational, verifiable unit of memory.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryNode {
    pub node_id: String,
    pub entity: String,
    pub content: String,
    #[serde(default)]
    pub relationships: Vec<Relationship>,
    /// Held as an ordered map so canonical serialization is deterministic.
    #[serde(default)]
    pub metadata: Map<String, Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub embedding: Option<Vec<f32>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub crypto: Option<CryptoEnvelope>,
    /// Server-reported verification status (present on some responses only).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub verified: Option<bool>,
}

impl MemoryNode {
    /// Construct an unsigned, un-embedded node ready to be sealed.
    pub fn new(
        node_id: impl Into<String>,
        entity: impl Into<String>,
        content: impl Into<String>,
        relationships: Vec<Relationship>,
        metadata: Map<String, Value>,
    ) -> Self {
        Self {
            node_id: node_id.into(),
            entity: entity.into(),
            content: content.into(),
            relationships,
            metadata,
            embedding: None,
            crypto: None,
            verified: None,
        }
    }
}

/// Coerce an arbitrary JSON value into a metadata object (empty if not an object).
pub fn to_metadata(value: Value) -> Map<String, Value> {
    match value {
        Value::Object(map) => map,
        _ => Map::new(),
    }
}
