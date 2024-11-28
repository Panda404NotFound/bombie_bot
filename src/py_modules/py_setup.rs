use std::env;
use std::path::PathBuf;
use std::process::Command;
use anyhow::{Result, anyhow};
use log::{info, error, debug};
use pyo3::Python;
use glob::glob;

pub struct PythonSetup {
    venv_path: PathBuf,
    requirements_path: PathBuf,
}

impl PythonSetup {
    pub fn new() -> Result<Self> {
        let current_dir = env::current_dir()?;
        Ok(Self {
            venv_path: current_dir.join("python_env"),
            requirements_path: current_dir.join("requirements.txt"),
        })
    }

    pub fn ensure_environment(&self) -> Result<()> {
        info!("Проверка Python окружения...");

        // Создаем виртуальное окружение, если его нет
        if !self.venv_path.exists() {
            self.create_virtual_environment()?;
        }

        // Настраиваем путь для кэша Playwright
        let playwright_cache = env::current_dir()?.join("target").join("playwright-cache");
        env::set_var("PLAYWRIGHT_BROWSERS_PATH", playwright_cache.to_str().unwrap());

        // Добавляем окружение Python
        Python::with_gil(|py| {
            let sys = py.import("sys")?;
            let current_dir = std::env::current_dir()?;
            let python_path = current_dir.join("src").join("python");
            sys.getattr("path")?.call_method1("append", (python_path.to_str(),))?;
            Ok::<_, anyhow::Error>(())
        })?;
        
        // Настраиваем пути Python
        self.setup_python_paths()?;
        
        // Проверяем и устанавливаем зависимости
        self.install_dependencies()?;

        // Устанавливаем браузеры Playwright
        self.setup_playwright()?;
        
        // Проверяем модули
        self.verify_modules()?;

        Ok(())
    }

    fn create_virtual_environment(&self) -> Result<()> {
        info!("Создание виртуального окружения Python...");
        
        // Определяем команду python3 в зависимости от платформы
        let python_cmd = if cfg!(windows) { "python" } else { "python3" };

        // Проверяем версию Python
        let version_output = Command::new(python_cmd)
            .arg("--version")
            .output()?;

        if !version_output.status.success() {
            return Err(anyhow!("Python3 не установлен"));
        }

        debug!("Используется Python: {}", String::from_utf8_lossy(&version_output.stdout));

        // Создаем виртуальное окружение
        let status = Command::new(python_cmd)
            .args(&["-m", "venv", self.venv_path.to_str().unwrap()])
            .status()?;

        if !status.success() {
            return Err(anyhow!("Не удалось создать виртуальное окружение"));
        }

        info!("Виртуальное окружение успешно создано");

        // Обновляем pip в виртуальном окружении
        let pip_path = if cfg!(windows) {
            self.venv_path.join("Scripts").join("pip.exe")
        } else {
            self.venv_path.join("bin").join("pip")
        };

        let status = Command::new(pip_path)
            .args(&["install", "--upgrade", "pip"])
            .status()?;

        if !status.success() {
            return Err(anyhow!("Не удалось обновить pip"));
        }

        info!("Pip успешно обновлен");
        Ok(())
    }

    fn setup_playwright(&self) -> Result<()> {
        info!("Установка браузеров Playwright...");
        
        let python_path = if cfg!(windows) {
            self.venv_path.join("Scripts").join("python.exe")
        } else {
            self.venv_path.join("bin").join("python")
        };

        // Настраиваем путь для кэша Playwright внутри виртуального окружения
        let playwright_cache = self.venv_path.join("playwright-cache");
        env::set_var("PLAYWRIGHT_BROWSERS_PATH", playwright_cache.to_str().unwrap());

        // Проверяем наличие браузеров через glob
        let browser_pattern = playwright_cache.join("chromium-*");
        let browser_exists = glob(browser_pattern.to_str().unwrap())?
            .next()
            .is_some();

        if !browser_exists {
            info!("Браузеры Playwright не найдены, выполняем установку...");
            
            // Устанавливаем браузеры через playwright install
            let status = Command::new(&python_path)
                .args(&["-m", "playwright", "install", "chromium"])
                .env("PLAYWRIGHT_BROWSERS_PATH", playwright_cache.to_str().unwrap())
                .status()?;

            if !status.success() {
                return Err(anyhow!("Ошибка установки браузеров Playwright"));
            }

            // Устанавливаем зависимости системы для браузеров
            let status = Command::new(&python_path)
                .args(&["-m", "playwright", "install-deps", "chromium"])
                .env("PLAYWRIGHT_BROWSERS_PATH", playwright_cache.to_str().unwrap())
                .status()?;

            if !status.success() {
                return Err(anyhow!("Ошибка установки зависимостей браузеров"));
            }

            info!("Браузеры Playwright успешно установлены");
        } else {
            info!("Браузеры Playwright уже установлены");
        }

        Ok(())
    }

    fn setup_python_paths(&self) -> Result<()> {
        // Определяем версию Python динамически
        let python_version = self.get_python_version()?;
        info!("Обнаружена версия Python: {}", python_version);
        
        // Корректное определение путей с учетом Windows
        let venv_site_packages = if cfg!(windows) {
            self.venv_path.join("Lib").join("site-packages")
        } else {
            self.venv_path
                .join("lib")
                .join(format!("python{}", python_version))
                .join("site-packages")
        };

        let venv_bin = if cfg!(windows) {
            self.venv_path.join("Scripts")
        } else {
            self.venv_path.join("bin")
        };

        // Проверка существования директории с корректной обработкой ошибок для Windows
        if !venv_site_packages.exists() {
            error!("Site-packages path not found: {}", venv_site_packages.display());
            return Err(anyhow!(
                "Директория site-packages не существует: {}",
                venv_site_packages.display()
            ));
        }

        // Корректная настройка PATH для Windows
        let path = env::var("PATH").unwrap_or_default();
        let path_separator = if cfg!(windows) { ";" } else { ":" };
        let new_path = format!("{}{}{}", venv_bin.display(), path_separator, path);
        env::set_var("PATH", new_path);

        // Настройка PYTHONPATH с учетом Windows-путей
        let pythonpath = venv_site_packages.to_str().ok_or_else(|| 
            anyhow!("Невалидный путь site-packages")
        )?;
        env::set_var("PYTHONPATH", &pythonpath);
        info!("Установлен PYTHONPATH: {}", pythonpath);

        // Настраиваем VIRTUAL_ENV
        env::set_var("VIRTUAL_ENV", self.venv_path.to_str().unwrap());

        // Проверяем настройку путей
        Python::with_gil(|py| {
            let sys = py.import("sys")?;
            let paths: Vec<String> = sys.getattr("path")?.extract()?;
            info!("Текущие пути Python: {:?}", paths);
            
            // Добавляем все необходимые пути
            let current_dir = env::current_dir()?;
            let paths_to_add = vec![
                pythonpath.to_string(),
                current_dir.join("src").join("python").to_str()
                    .ok_or_else(|| anyhow!("Невалидный путь python"))?.to_string(),
                current_dir.to_str()
                    .ok_or_else(|| anyhow!("Невалидный путь current_dir"))?.to_string(),
            ];

            for path in paths_to_add {
                if !paths.iter().any(|p| p == &path) {
                    sys.getattr("path")?.call_method1("append", (&path,))?;
                    info!("Добавлен путь в sys.path: {}", path);
                }
            }
            
            Ok::<(), anyhow::Error>(())
        })?;

        Ok(())
    }

    fn verify_modules(&self) -> Result<()> {
        Python::with_gil(|py| {
            info!("Проверка импорта модулей...");
            
            // Выводим текущие пути Python
            let sys = py.import("sys")?;
            let paths: Vec<String> = sys.getattr("path")?.extract()?;
            info!("Пути Python перед импортом: {:?}", paths);
            
            // Пробуем импортировать telethon
            match py.import("telethon") {
                Ok(_) => {
                    info!("Модуль telethon успешно импортирован");
                    Ok(())
                },
                Err(e) => {
                    error!("Ошибка импорта telethon: {}", e);
                    error!("Текущая директория: {:?}", env::current_dir()?);
                    error!("PYTHONPATH: {:?}", env::var("PYTHONPATH"));
                    Err(anyhow!("Не удалось импортировать telethon: {}", e))
                }
            }
        })
    }

    fn install_dependencies(&self) -> Result<()> {
        let pip_path = if cfg!(windows) {
            self.venv_path.join("Scripts").join("pip.exe")
        } else {
            self.venv_path.join("bin").join("pip")
        };

        info!("Установка зависимостей из {:?}", self.requirements_path);
        
        let status = Command::new(&pip_path)
            .args(&[
                "install",
                "-r",
                self.requirements_path.to_str().unwrap()
            ])
            .status()?;

        if !status.success() {
            return Err(anyhow!("Не удалось установить зависимости"));
        }

        Ok(())
    }

    // Добавляем новый метод для определения версии Python
    fn get_python_version(&self) -> Result<String> {
        let python_path = if cfg!(windows) {
            self.venv_path.join("Scripts").join("python.exe")
        } else {
            self.venv_path.join("bin").join("python")
        };

        let output = Command::new(&python_path)
            .args(&["--version"])
            .output()?;

        if !output.status.success() {
            return Err(anyhow!("Не удалось определить версию Python"));
        }

        let version_string = String::from_utf8(output.stdout)?;
        // Извлекаем только основную версию (например, "3.13" из "Python 3.13.0")
        let version = version_string
            .split_whitespace()
            .nth(1)
            .ok_or_else(|| anyhow!("Неверный формат версии Python"))?
            .split('.')
            .take(2)
            .collect::<Vec<&str>>()
            .join(".");

        Ok(version)
    }
}
