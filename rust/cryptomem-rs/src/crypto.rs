//! Canonical hashing and Ed25519 signing, byte-compatible with the Python engine.
//!
//! The canonical form is a compact JSON object over exactly the identity-bearing
//! fields (`content`, `entity`, `metadata`, `relationships`) with sorted keys and
//! relationships sorted as `[type, target_id]` pairs — identical to
//! `cryptomem.crypto.hashing.canonical_bytes` on the Python side.

use std::collections::BTreeMap;

use ed25519_dalek::{Signature, Signer as _, SigningKey, Verifier, VerifyingKey};
use serde_json::Value;
use sha2::{Digest, Sha256};

use crate::error::Error;
use crate::models::{CryptoEnvelope, MemoryNode};

/// Serialize a node's identity-bearing fields deterministically.
pub fn canonical_bytes(node: &MemoryNode) -> Vec<u8> {
    let mut rels: Vec<[&str; 2]> = node
        .relationships
        .iter()
        .map(|r| [r.rel_type.as_str(), r.target_id.as_str()])
        .collect();
    rels.sort_unstable();

    // A BTreeMap guarantees sorted top-level keys regardless of any
    // serde_json feature flags pulled in elsewhere in the dependency graph.
    let mut payload: BTreeMap<&str, Value> = BTreeMap::new();
    payload.insert("entity", Value::String(node.entity.clone()));
    payload.insert("content", Value::String(node.content.clone()));
    payload.insert(
        "relationships",
        serde_json::to_value(&rels).expect("relationships serialize"),
    );
    payload.insert("metadata", Value::Object(node.metadata.clone()));

    serde_json::to_vec(&payload).expect("canonical payload serializes")
}

/// Hex SHA-256 digest of a node's canonical bytes.
pub fn sha256_hex(node: &MemoryNode) -> String {
    hex::encode(Sha256::digest(canonical_bytes(node)))
}

/// Verify an Ed25519 signature over a hex digest. Returns `false` on any error.
pub fn verify(public_key_ref: &str, digest_hex: &str, signature_hex: &str) -> bool {
    let Ok(pk_bytes) = hex::decode(public_key_ref) else {
        return false;
    };
    let Ok(pk): Result<[u8; 32], _> = pk_bytes.try_into() else {
        return false;
    };
    let Ok(vk) = VerifyingKey::from_bytes(&pk) else {
        return false;
    };
    let Ok(sig_bytes) = hex::decode(signature_hex) else {
        return false;
    };
    let Ok(sig): Result<[u8; 64], _> = sig_bytes.try_into() else {
        return false;
    };
    let signature = Signature::from_bytes(&sig);
    vk.verify(digest_hex.as_bytes(), &signature).is_ok()
}

/// Re-derive a node's hash and check its signature end to end.
pub fn verify_node(node: &MemoryNode) -> bool {
    match &node.crypto {
        Some(env) => {
            sha256_hex(node) == env.hash && verify(&env.public_key_ref, &env.hash, &env.signature)
        }
        None => false,
    }
}

/// An Ed25519 signer compatible with PyNaCl's hex-seed key format.
pub struct Signer {
    sk: SigningKey,
}

impl Signer {
    /// Load a signer from a 32-byte hex seed (the same seed PyNaCl uses).
    pub fn from_seed_hex(seed_hex: &str) -> Result<Self, Error> {
        let bytes = hex::decode(seed_hex).map_err(|e| Error::Crypto(e.to_string()))?;
        let seed: [u8; 32] = bytes
            .try_into()
            .map_err(|_| Error::Crypto("seed must be 32 bytes".into()))?;
        Ok(Self {
            sk: SigningKey::from_bytes(&seed),
        })
    }

    /// Generate a fresh in-memory key from the OS CSPRNG.
    pub fn generate() -> Self {
        use rand::rngs::OsRng;
        Self {
            sk: SigningKey::generate(&mut OsRng),
        }
    }

    /// Hex-encoded public key, used as the envelope's `public_key_ref`.
    pub fn public_key_hex(&self) -> String {
        hex::encode(self.sk.verifying_key().to_bytes())
    }

    /// Sign a hex digest, returning a hex-encoded signature.
    pub fn sign_digest(&self, digest_hex: &str) -> String {
        hex::encode(self.sk.sign(digest_hex.as_bytes()).to_bytes())
    }

    /// Hash, sign, and attach a [`CryptoEnvelope`] to `node` in place.
    pub fn seal(&self, node: &mut MemoryNode) {
        node.crypto = None;
        let hash = sha256_hex(node);
        let signature = self.sign_digest(&hash);
        node.crypto = Some(CryptoEnvelope {
            hash,
            signature,
            public_key_ref: self.public_key_hex(),
            merkle_root: None,
        });
    }
}
