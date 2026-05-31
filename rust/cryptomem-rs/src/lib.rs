//! Typed Rust client for the **cryptomem** verified-memory sidecar.
//!
//! The headline feature is *cross-language cryptographic compatibility*: a node
//! signed in Rust with [`crypto::Signer`] reproduces the exact SHA-256 canonical
//! hash and Ed25519 signature the Python engine produces, so it can be POSTed to
//! `/cmem/v1/memory/signed` and the server will verify it (zero-trust ingest).
//!
//! ```no_run
//! use cryptomem_rs::{CryptoMemClient, crypto::Signer};
//! use serde_json::json;
//!
//! # fn main() -> Result<(), cryptomem_rs::Error> {
//! let client = CryptoMemClient::new("http://127.0.0.1:8088")
//!     .with_signer(Signer::generate());
//!
//! // Signed locally, verified remotely.
//! let node = client.archive_signed(
//!     "Project Phoenix",
//!     "Budget approved at 4.2M for FY26.",
//!     vec![],
//!     json!({ "source": "Q3.pdf" }),
//! )?;
//! assert_eq!(node.verified, Some(true));
//! # Ok(()) }
//! ```

pub mod crypto;
pub mod error;
pub mod models;

#[cfg(feature = "http")]
pub mod client;

pub use error::Error;
pub use models::{CryptoEnvelope, MemoryNode, Relationship};

#[cfg(feature = "http")]
pub use client::{ChatResult, CryptoMemClient, QueryResult};
