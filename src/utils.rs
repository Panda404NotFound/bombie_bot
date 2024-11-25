use anyhow::{Result, anyhow};
use log::{info, error};
use pyo3::Python;
use std::fs;
use crate::py_modules::py_imports::get_import_name;
// use crate::emulation::{get_device_metadata, get_device_browser, EmulatedBrowser};
use std::env;

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

/// Удаляет директории logs и recordings если они существуют
pub fn delete_logs() -> Result<()> {
    let should_delete = env::var("DELETE_LOG_FIRST_START")
        .unwrap_or_else(|_| "false".to_string())
        .parse::<bool>()
        .unwrap_or(false);

    if !should_delete {
        info!("Пропуск удаления логов (DELETE_LOG_FIRST_START=false)");
        return Ok(());
    }

    let current_dir = std::env::current_dir()?;
    let dirs_to_delete = ["logs", "recordings"];

    for dir in dirs_to_delete.iter() {
        let path = current_dir.join(dir);
        if path.exists() {
            info!("Удаление директории: {}", path.display());
            match fs::remove_dir_all(&path) {
                Ok(_) => info!("Успешно удалена директория: {}", dir),
                Err(e) => error!("Ошибка при удалении директории {}: {}", dir, e)
            }
        } else {
            info!("Директория {} не найдена, пропуск", dir);
        }
    }

    Ok(())
}