use std::collections::HashMap;
use once_cell::sync::Lazy;

/// Карта специальных случаев импорта пакетов
static PACKAGE_IMPORT_EXCEPTIONS: Lazy<HashMap<&str, &str>> = Lazy::new(|| {
    let mut m = HashMap::new();
    m.insert("python-dotenv", "dotenv");
    m.insert("ffmpeg-python", "ffmpeg");
    m.insert("beautifulsoup4", "bs4");
    m.insert("selectolax", "selectolax.parser");
    m.insert("Pillow", "PIL");
    m.insert("opentelemetry-api", "opentelemetry");
    m.insert("wrapt", "wrapt");
    m.insert("opentelemetry-sdk", "opentelemetry.sdk");
    m.insert("opentelemetry-instrumentation", "opentelemetry.instrumentation");
    m.insert("opentelemetry-semantic-conventions", "opentelemetry.semantic_conventions");
    m.insert("opencv-python", "cv2");
    m
});

/// Получает корректное имя пакета для импорта
pub fn get_import_name(package: &str) -> &str {
    PACKAGE_IMPORT_EXCEPTIONS
        .get(package)
        .copied()
        .unwrap_or(package)
}