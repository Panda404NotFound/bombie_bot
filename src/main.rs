mod py_modules;
mod utils;
mod py_automation;

use anyhow::Result;
use dotenv::dotenv;
use log::{error, info};
use nix::sys::signal::{self, Signal};
use nix::unistd::Pid;
use tokio::signal::ctrl_c;
#[allow(unused_imports)]
use pyo3::Python;
#[allow(unused_imports)]
use anyhow::anyhow;
#[allow(unused_imports)]
use crate::py_modules::py_setup::PythonSetup;
#[allow(unused_imports)]
use crate::utils::{try_import_package, parse_requirements};
use std::fs;

#[tokio::main]
async fn main() -> Result<()> {
    env_logger::init();
    info!("Запуск WebApp Analyzer...");

    dotenv().ok();

    // Удаление логов при необходимости
    if let Err(e) = utils::delete_logs() {
        error!("Ошибка при удалении логов: {}", e);
    }

    // Ждем 1 секунду для завершения удаления логов
    tokio::time::sleep(std::time::Duration::from_secs(1)).await;

    // Spawn CTRL+C handler
    let pid = std::process::id() as i32;
    tokio::spawn(async move {
        if let Ok(()) = ctrl_c().await {
            info!("Получен сигнал Ctrl+C, завершаем работу...");
            if let Err(e) = signal::kill(Pid::from_raw(pid), Signal::SIGTERM) {
                error!("Ошибка отправки SIGTERM: {}", e);
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