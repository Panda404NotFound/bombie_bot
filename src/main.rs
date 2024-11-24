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
// #[allow(unused_imports)]
// use crate::emulation::{initialize_emulation, get_device_metadata, get_device_browser};
#[allow(unused_imports)]
use crate::utils::{try_import_package, parse_requirements};
use std::fs;

#[tokio::main]
async fn main() -> Result<()> {
    env_logger::init();
    info!("Запуск WebApp Analyzer...");

    dotenv().ok();

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

    /*
    // Инициализируем эмуляцию устройств
    info!("Инициализация эмуляции устройств...");
    initialize_emulation().await?;
    info!("Эмуляция устройств успешно инициализирована");

    // Логируем информацию об эмулированных устройствах
    let devices = ["ios_device", "android_device"];
    for device_id in devices {
        log_device_info(device_id).await?;
    }

    // Получаем метаданные и браузер для устройства
    let device_id = "android_device";
    let device_metadata = get_device_metadata(device_id).await?;
    let browser = get_device_browser(device_id).await?;

    // Регистрируем устройство
    // let registrar = register::TelegramRegistrar::new(device_metadata.clone(), browser.as_ref().clone())?;
    // registrar.start_reg().await?;

    // Выполняем вход пользователя
    // let loging = login::TelegramLogin::new(device_metadata, browser.as_ref().clone())?;
    // loging.connect().await?;

    // Выполняем вход пользователя и поиск бота
    // let login = login::TelegramLogin::new(device_metadata, browser.as_ref().clone())?;
    // login.run_bot_handle().await?;

    // Запускаем Mini App и выполняем вход пользователя
    let login = login::TelegramLogin::new(device_metadata, browser.as_ref().clone())?;
    login.start_app().await?;

    */

    // Запуск автоматизации
    info!("Запуск автоматизации...");
    if let Err(e) = py_automation::run_automation().await {
        error!("Ошибка автоматизации: {}", e);
        return Err(e);
    }

    Ok(())

}