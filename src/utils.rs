use anyhow::{Result, anyhow};
use log::info;
use pyo3::Python;
use std::fs;
use crate::py_modules::py_imports::get_import_name;
// use crate::emulation::{get_device_metadata, get_device_browser, EmulatedBrowser};

// Пытается импортировать пакет с различными вариантами написания имени
pub fn try_import_package(py: Python<'_>, package: &str) -> Result<()> {
    // Проверяем специальные случаи импорта
    let import_name = get_import_name(package);
    if py.import(import_name).is_ok() {
        return Ok(());
    }

    // Пробуем стандартный вариант
    if py.import(package).is_ok() {
        return Ok(());
    }

    // Пробуем вариант с подчеркиваниями
    let underscore_name = package.replace('-', "_");
    if underscore_name != package && py.import(&*underscore_name).is_ok() {
        return Ok(());
    }

    // Если все попытки не удались, возвращаем ошибку
    Err(anyhow!(
        "Не удалось импортировать пакет '{}' (пробовал варианты: {}, {}, {})",
        package,
        import_name,
        package,
        underscore_name
    ))
}

/// Парсит файл requirements.txt и возвращает список пакетов
pub fn parse_requirements() -> Result<Vec<String>> {
    info!("Парсинг requirements.txt...");
    let requirements = fs::read_to_string("requirements.txt")?;
    Ok(requirements
        .lines()
        .filter(|line| !line.trim().is_empty())
        .map(|line| {
            line.split(['=', '>', '<', '~'])
                .next()
                .unwrap_or("")
                .trim()
                .to_string()
        })
        .filter(|pkg| !pkg.is_empty())
        .collect())
}

/*
// Логирует информацию об эмулируемом устройстве
pub async fn log_device_info(device_id: &str) -> Result<()> {
    if let Ok(metadata) = get_device_metadata(device_id).await {
        info!(
            "Устройство {}: \n\
             - Платформа: {:?}\n\
             - Модель: {}\n\
             - Версия: {}\n\
             - Разрешение: {}x{}\n\
             - User Agent: {}\n\
             - Сеть: {}",
            device_id,
            metadata.platform,
            metadata.device_id,
            metadata.user_agent,
            metadata.screen_metrics.width,
            metadata.screen_metrics.height,
            metadata.webview_data.engine_version,
            metadata.connection_info.network_type
        );

        if let Ok(browser) = get_device_browser(device_id).await {
            info!(
                "Браузер для {}: {:?}",
                device_id,
                match browser.as_ref() {
                    EmulatedBrowser::Webkit(_) => "WebKit",
                    EmulatedBrowser::ChromiumBased(_) => "Chromium",
                }
            );
        }
    }
    Ok(())
}
*/