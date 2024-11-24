use anyhow::{Result, anyhow};
use log::{info, error};
#[allow(unused_imports)]
use pyo3::{Python, PyResult, types::IntoPyDict};
use tokio::time::timeout;
use std::time::Duration;

pub async fn run_automation() -> Result<()> {
    info!("Запуск автоматизации...");
    
    // Создаем Python контекст с таймаутом
    match timeout(Duration::from_secs(30), async {
        Python::with_gil(|py| -> PyResult<()> {
            let automation_module = py.import("action")?;
            
            // Вызываем initialize_automation без параметров, 
            // так как теперь она сама инициализирует логин
            let coroutine = automation_module
                .getattr("initialize_automation")?
                .call0()?;
            
            // Запускаем корутину
            py.import("asyncio")?
                .getattr("run")?
                .call1((coroutine,))?;
            
            Ok(())
        })
    }).await {
        Ok(result) => match result {
            Ok(_) => {
                info!("Автоматизация успешно завершена");
                Ok(())
            },
            Err(e) => {
                error!("Ошибка при выполнении автоматизации: {:?}", e);
                Err(anyhow!("Python error: {:?}", e))
            }
        },
        Err(_) => {
            error!("Таймаут выполнения автоматизации");
            Err(anyhow!("Таймаут автоматизации"))
        }
    }
}