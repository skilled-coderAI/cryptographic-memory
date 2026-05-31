//! Error type for the crate.

use thiserror::Error;

#[derive(Debug, Error)]
pub enum Error {
    #[error("crypto error: {0}")]
    Crypto(String),

    #[error("serialization error: {0}")]
    Json(#[from] serde_json::Error),

    #[cfg(feature = "http")]
    #[error("http transport error: {0}")]
    Http(#[from] reqwest::Error),

    #[error("api error {status}: {body}")]
    Api { status: u16, body: String },
}
