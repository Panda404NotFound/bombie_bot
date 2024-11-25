mod py_modules;
mod utils;
mod py_automation;
mod platform_specific;
mod config;
mod errors;

use std::fs;
use std::sync::Arc;
use anyhow::Result;
use dotenv::dotenv;
use log::{error, info};
use tokio::signal::ctrl_c;

use config::{SystemConfig, ShutdownState};
use errors::ShutdownError;

#[allow(unused_imports)]
use pyo3::Python;

#[allow(unused_imports)]
use anyhow::anyhow;

#[allow(unused_imports)]
use crate::py_modules::py_setup::PythonSetup;

#[allow(unused_imports)]
use crate::utils::{try_import_package, parse_requirements};

#[tokio::main]
async fn main() -> Result<()> {
    env_logger::init();
    info!("Запуск WebApp Analyzer...");

    dotenv().ok();

    // Удаление логов при необходимости
    if let Err(e) = utils::delete_logs() {
        error!("Ошибка при удалении логов: {}", e);
    }

    let config = Arc::new(SystemConfig::new());
    let pid = std::process::id() as i32;

    // Обработчик Ctrl+C
    let config_clone = Arc::clone(&config);
    tokio::spawn(async move {
        if let Ok(()) = ctrl_c().await {
            info!("Initiating graceful shutdown...");
            
            let result = async {
                #[cfg(unix)]
                platform_specific::unix::handle_shutdown(&config_clone, pid).await?;
                
                #[cfg(windows)]
                platform_specific::windows::handle_shutdown(&config_clone, pid).await?;
                
                platform_specific::cleanup::cleanup_resources(&config_clone).await?;
                config_clone.set_shutdown_state(ShutdownState::Completed);
                Ok::<(), ShutdownError>(())
            }.await;

            if let Err(e) = result {
                error!("Critical shutdown error: {}", e);
                std::process::exit(1);
            }
        }
    });

    // Инициализируем Python окружение
    let python_setup = PythonSetup::new()?;
    python_setup.ensure_environment()?;

    // Создаем директорию для кэша Playwright и проверяем установку
    let playwright_cache = std::env::current_dir()?.join("target").join("playwright-cache");
    if !playwright_cache.exists() {
        fs::create_dir_all(&playwright_cache)?;
    }

    // Проверяем установку Playwright в виртуальном окружении
    Python::with_gil(|py| {
        let sys = py.import("sys")?;
        let paths: Vec<String> = sys.getattr("path")?.extract()?;
        info!("Python paths: {:?}", paths);
        
        if let Err(e) = py.import("playwright") {
            error!("Ошибка импорта playwright: {}", e);
            return Err(anyhow!("Playwright не установлен корректно"));
        }
        Ok(())
    })?;

    // Проверяем все необходимые Python импорты
    let required_packages = parse_requirements()?;
    Python::with_gil(|py| {
        for package in &required_packages {
            if let Err(e) = try_import_package(py, package) {
                error!("Ошибка импорта пакета {}: {}", package, e);
                return Err(anyhow!("Ошибка импорта: {}", e));
            }
        }
        Ok(())
    })?;

    // Запуск автоматизации
    info!("Запуск автоматизации...");
    if let Err(e) = py_automation::run_automation().await {
        error!("Ошибка автоматизации: {}", e);
        return Err(e);
    }

    Ok(())

}