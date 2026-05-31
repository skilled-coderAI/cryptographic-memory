//! Cross-language crypto vectors.
//!
//! The constants below were produced by the Python engine
//! (`cryptomem.crypto.hashing` + `cryptomem.crypto.signer`). These tests fail if
//! the Rust canonicalization, hashing, or signing ever drifts from Python, which
//! would break server-side verification of Rust-signed nodes.

use cryptomem_rs::crypto::{canonical_bytes, sha256_hex, verify, verify_node, Signer};
use cryptomem_rs::models::{to_metadata, MemoryNode, Relationship};
use serde_json::json;

const CANONICAL: &str = r#"{"content":"Budget approved at 4.2M for FY26.","entity":"Project Phoenix","metadata":{"source":"Q3.pdf","timestamp":"2026-01-01T00:00:00+00:00"},"relationships":[["author","mem_alice"],["owned_by","mem_bob"]]}"#;
const SEED: &str = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f";
const PUBKEY: &str = "03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8";
const DIGEST: &str = "da7030c307bbd400c23eb04482d89ba1df8aaa294a84fb86c3e6de626925a194";
const SIGNATURE: &str = "b505f0e9d517bc93161f098f16e8897539faaba8d922c75b773f9ccb4f6545cb678bd01b0b437b0a94059b016836d17b846e55e2ce3737eeedf38da89ef8870b";

fn fixture_node() -> MemoryNode {
    MemoryNode::new(
        "mem_test",
        "Project Phoenix",
        "Budget approved at 4.2M for FY26.",
        vec![
            // Deliberately unsorted to exercise canonical ordering.
            Relationship::new("owned_by", "mem_bob"),
            Relationship::new("author", "mem_alice"),
        ],
        to_metadata(json!({
            "source": "Q3.pdf",
            "timestamp": "2026-01-01T00:00:00+00:00",
        })),
    )
}

#[test]
fn canonical_matches_python() {
    let bytes = canonical_bytes(&fixture_node());
    assert_eq!(String::from_utf8(bytes).unwrap(), CANONICAL);
}

#[test]
fn digest_matches_python() {
    assert_eq!(sha256_hex(&fixture_node()), DIGEST);
}

#[test]
fn signer_reproduces_python_key_and_signature() {
    let signer = Signer::from_seed_hex(SEED).unwrap();
    assert_eq!(signer.public_key_hex(), PUBKEY);
    assert_eq!(signer.sign_digest(DIGEST), SIGNATURE);
}

#[test]
fn verifies_python_signature() {
    assert!(verify(PUBKEY, DIGEST, SIGNATURE));
}

#[test]
fn seal_then_verify_round_trips() {
    let signer = Signer::from_seed_hex(SEED).unwrap();
    let mut node = fixture_node();
    signer.seal(&mut node);

    let env = node.crypto.clone().expect("sealed node has an envelope");
    assert_eq!(env.hash, DIGEST);
    assert_eq!(env.public_key_ref, PUBKEY);
    assert_eq!(env.signature, SIGNATURE);
    assert!(verify_node(&node));
}

#[test]
fn tampered_content_fails_verification() {
    let signer = Signer::from_seed_hex(SEED).unwrap();
    let mut node = fixture_node();
    signer.seal(&mut node);

    node.content = "Budget secretly raised to 9.9M.".into();
    assert!(!verify_node(&node));
}

#[test]
fn generated_signer_round_trips() {
    let signer = Signer::generate();
    let mut node = fixture_node();
    signer.seal(&mut node);
    assert!(verify_node(&node));
}
