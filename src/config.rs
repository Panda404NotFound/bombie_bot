use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::Arc;

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ShutdownState {
    Running = 0,
    ShuttingDown = 1,
    Completed = 2,
}

#[derive(Debug)]
pub struct SystemConfig {
    shutdown_signal: Arc<AtomicBool>,
    shutdown_state: Arc<AtomicUsize>,
}

impl SystemConfig {
    pub fn new() -> Self {
        Self {
            shutdown_signal: Arc::new(AtomicBool::new(false)),
            shutdown_state: Arc::new(AtomicUsize::new(ShutdownState::Running as usize)),
        }
    }

    pub fn request_shutdown(&self) -> anyhow::Result<()> {
        self.shutdown_signal.store(true, Ordering::SeqCst);
        self.set_shutdown_state(ShutdownState::ShuttingDown);
        Ok(())
    }

    pub fn set_shutdown_state(&self, state: ShutdownState) {
        self.shutdown_state.store(state as usize, Ordering::SeqCst);
    }
}