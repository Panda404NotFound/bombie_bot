use crate::config::SystemConfig;
use anyhow::Result;
use log::{error, info};
use pyo3::Python;

pub mod cleanup {
    use super::*;
    use std::time::Duration;
    use tokio::time::timeout;
    use std::fs;

    pub async fn cleanup_resources(_config: &SystemConfig) -> Result<()> {
        const CLEANUP_TIMEOUT: Duration = Duration::from_secs(5);
        
        timeout(CLEANUP_TIMEOUT, async {
            info!("Starting cleanup process...");
            
            // Очистка Python ресурсов
            Python::with_gil(|py| {
                if let Err(e) = py.run("import gc; gc.collect()", None, None) {
                    error!("Python cleanup error: {}", e);
                }
            });

            // Очистка кэша
            let cache_path = std::env::current_dir()?.join("target").join("playwright-cache");
            if cache_path.exists() {
                if let Err(e) = fs::remove_dir_all(&cache_path) {
                    error!("Cache cleanup error: {}", e);
                }
            }

            info!("Cleanup completed");
            Ok(())
        })
        .await
        .map_err(|_| anyhow::anyhow!("Cleanup timeout exceeded"))?
    }
}

#[cfg(unix)]
pub mod unix {
    use super::*;
    use nix::sys::signal::{self, Signal};
    use nix::unistd::Pid;

    pub async fn handle_shutdown(config: &SystemConfig, pid: i32) -> Result<()> {
        info!("Handling Unix shutdown...");
        if let Err(e) = signal::kill(Pid::from_raw(pid), Signal::SIGTERM) {
            error!("SIGTERM error: {}", e);
            return Err(anyhow::anyhow!("Failed to send SIGTERM: {}", e));
        }
        config.request_shutdown()?;
        Ok(())
    }
}

#[cfg(windows)]
pub mod windows {
    use super::*;
    use windows_sys::Win32::Foundation::CloseHandle;
    use windows_sys::Win32::System::Threading::{OpenProcess, TerminateProcess, PROCESS_TERMINATE};

    pub async fn handle_shutdown(config: &SystemConfig, pid: i32) -> Result<()> {
        info!("Handling Windows shutdown...");
        
        unsafe {
            let handle = OpenProcess(
                PROCESS_TERMINATE,
                0,                
                pid as u32 
            );
            
            if handle == 0 {
                return Err(anyhow::anyhow!("Failed to get process handle"));
            }

            let terminate_result = TerminateProcess(handle, 0);
            let close_result = CloseHandle(handle);

            if terminate_result == 0 {
                return Err(anyhow::anyhow!("Failed to terminate process"));
            }

            if close_result == 0 {
                return Err(anyhow::anyhow!("Failed to close handle"));
            }
        }

        config.request_shutdown()?;
        Ok(())
    }
}