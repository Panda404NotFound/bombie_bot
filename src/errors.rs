use thiserror::Error;

#[derive(Debug, Error)]
pub enum ShutdownError {
    #[error("Platform error: {0}")]
    PlatformError(#[from] anyhow::Error),
}