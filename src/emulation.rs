use anyhow::{Result, anyhow};
use std::sync::Arc;
use log::info;
use tokio::sync::RwLock;
use chromiumoxide::BrowserConfig;
use serde::{Serialize, Deserialize};
use std::collections::HashMap;
use once_cell::sync::OnceCell;

// Глобальное состояние эмулируемых устройств
static GLOBAL_DEVICES: OnceCell<Arc<RwLock<DeviceManager>>> = OnceCell::new();

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceMetadata {
    pub device_id: String,
    pub platform: PlatformType,
    pub user_agent: String,
    pub app_version: String,
    pub screen_metrics: ScreenMetrics,
    pub language: String,
    pub lang_code: String,
    pub timezone: String,
    pub webview_data: WebViewData,
    pub hardware_info: HardwareInfo,
    pub connection_info: ConnectionInfo,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScreenMetrics {
    pub width: u32,
    pub height: u32,
    pub pixel_ratio: f32,
    pub touch_points: u8,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WebViewData {
    pub engine_version: String,
    pub supported_apis: Vec<String>,
    webkit_flags: Option<WebKitFlags>,
    chrome_flags: Option<ChromeFlags>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareInfo {
    pub model: String,
    pub platform_version: String,
    pub memory: String,
    pub cpu_cores: u8,
    pub gpu_renderer: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectionInfo {
    pub network_type: String,
    pub bandwidth: String,
    pub rtt: u32,
    pub throughput: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PlatformType {
    IOS,
    Android,
}

#[derive(Debug)]
pub struct DeviceManager {
    pub devices: HashMap<String, EmulatedDevice>,
}

#[derive(Debug, Clone)]
pub struct EmulatedDevice {
    pub metadata: DeviceMetadata,
    pub browser: EmulatedBrowser,
}

#[allow(dead_code)]
#[derive(Debug, Clone)]
pub enum EmulatedBrowser {
    Webkit(WebKitConfig),
    ChromiumBased(ChromiumConfig),
}

#[allow(dead_code)]
#[derive(Debug, Clone)]
pub struct WebKitConfig {
    pub user_agent: String,
    pub webkit_version: String,
    pub platform_version: String,
    pub build_number: String,
}

#[allow(dead_code)]
#[derive(Debug, Clone)]
pub struct ChromiumConfig {
    pub user_agent: String,
    pub chrome_version: String,
    pub webview_version: String,
    pub build_version: String,
}

// Реализация менеджера устройств
impl DeviceManager {
    pub fn new() -> Self {
        Self {
            devices: HashMap::new(),
        }
    }

    pub async fn create_ios_device(&mut self, device_id: &str) -> Result<()> {
        let metadata = self.generate_ios_metadata(device_id)?;
        
        let webkit_config = WebKitConfig {
            user_agent: metadata.user_agent.clone(),
            webkit_version: "605.1.15".to_string(),
            platform_version: metadata.hardware_info.platform_version.clone(),
            build_number: "15E148".to_string(),
        };
        
        self.devices.insert(
            device_id.to_string(),
            EmulatedDevice {
                metadata: metadata.clone(),
                browser: EmulatedBrowser::Webkit(webkit_config),
            },
        );
        Ok(())
    }

    pub async fn create_android_device(&mut self, device_id: &str) -> Result<()> {
        let metadata = self.generate_android_metadata(device_id)?;
        
        let chrome_config = ChromiumConfig {
            user_agent: metadata.user_agent.clone(),
            chrome_version: "97.0.4692.98".to_string(),
            webview_version: metadata.webview_data.engine_version.clone(),
            build_version: "4692.98".to_string(),
        };
        
        self.devices.insert(
            device_id.to_string(),
            EmulatedDevice {
                metadata: metadata.clone(),
                browser: EmulatedBrowser::ChromiumBased(chrome_config),
            },
        );
        Ok(())
    }

    fn generate_ios_metadata(&self, device_id: &str) -> Result<DeviceMetadata> {
        Ok(DeviceMetadata {
            device_id: device_id.to_string(),
            platform: PlatformType::IOS,
            app_version: "11.3.1".to_string(),
            user_agent: "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1".to_string(),
            screen_metrics: ScreenMetrics {
                width: 390,
                height: 844,
                pixel_ratio: 3.0,
                touch_points: 5,
            },
            language: "en-US".to_string(),
            lang_code: "en".to_string(),
            timezone: "UTC".to_string(),
            webview_data: WebViewData {
                engine_version: "605.1.15".to_string(),
                supported_apis: vec![
                    "WebKit".to_string(),
                    "WebGL".to_string(),
                    "WebRTC".to_string(),
                ],
                webkit_flags: Some(WebKitFlags::default()),
                chrome_flags: None,
            },
            hardware_info: HardwareInfo {
                model: "iPhone 14 Pro".to_string(),
                platform_version: "iOS 11.3.1".to_string(),
                memory: "6GB".to_string(),
                cpu_cores: 6,
                gpu_renderer: "Apple GPU".to_string(),
            },
            connection_info: ConnectionInfo {
                network_type: "wifi".to_string(),
                bandwidth: "10mbps".to_string(),
                rtt: 50,
                throughput: 1000,
            },
        })
    }

    fn generate_android_metadata(&self, device_id: &str) -> Result<DeviceMetadata> {
        Ok(DeviceMetadata {
            device_id: device_id.to_string(),
            platform: PlatformType::Android,
            app_version: "11.3.1".to_string(),
            user_agent: "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.98 Mobile Safari/537.36".to_string(),
            screen_metrics: ScreenMetrics {
                width: 412,
                height: 915,
                pixel_ratio: 2.625,
                touch_points: 5,
            },
            language: "en-US".to_string(),
            lang_code: "en".to_string(),
            timezone: "UTC".to_string(),
            webview_data: WebViewData {
                engine_version: "97.0.4692.98".to_string(),
                supported_apis: vec![
                    "WebView".to_string(),
                    "WebGL".to_string(),
                    "WebRTC".to_string(),
                ],
                webkit_flags: None,
                chrome_flags: Some(ChromeFlags::default()),
            },
            hardware_info: HardwareInfo {
                model: "Samsung Galaxy S21 Ultra".to_string(),
                platform_version: "Android 13".to_string(),
                memory: "12GB".to_string(),
                cpu_cores: 8,
                gpu_renderer: "Adreno 660".to_string(),
            },
            connection_info: ConnectionInfo {
                network_type: "5g".to_string(),
                bandwidth: "20mbps".to_string(),
                rtt: 30,
                throughput: 2000,
            },
        })
    }
}

impl EmulatedBrowser {
    pub fn get_browser_config(&self, width: u32, height: u32) -> Result<BrowserConfig> {
        let config = match self {
            EmulatedBrowser::Webkit(webkit_config) => {
                BrowserConfig::builder()
                    .window_size(width, height)
                    .arg(format!("--user-agent={}", webkit_config.user_agent))
                    .arg("--disable-background-networking")
                    .arg("--disable-background-timer-throttling")
                    .arg("--disable-backgrounding-occluded-windows")
                    .arg("--disable-breakpad")
                    .arg("--disable-component-update")
                    .arg("--disable-default-apps")
                    .arg("--disable-dev-shm-usage")
                    .arg("--disable-domain-reliability")
                    .arg("--disable-extensions")
                    .arg("--disable-features=AudioServiceOutOfProcess")
                    .arg("--disable-hang-monitor")
                    .arg("--disable-ipc-flooding-protection")
                    .arg("--force-webview")
                    .arg("--metrics-recording-only")
                    .build()
                    .map_err(|e| anyhow!(e))?
            },
            EmulatedBrowser::ChromiumBased(chrome_config) => {
                BrowserConfig::builder()
                    .window_size(width, height)
                    .arg(format!("--user-agent={}", chrome_config.user_agent))
                    .arg("--disable-background-networking")
                    .arg("--disable-background-timer-throttling")
                    .arg("--disable-backgrounding-occluded-windows")
                    .arg("--disable-breakpad")
                    .arg("--disable-component-update")
                    .arg("--disable-default-apps")
                    .arg("--disable-dev-shm-usage")
                    .arg("--disable-domain-reliability")
                    .arg("--disable-extensions")
                    .arg("--disable-features=AudioServiceOutOfProcess")
                    .arg("--disable-hang-monitor")
                    .arg("--disable-ipc-flooding-protection")
                    .arg("--force-webview")
                    .arg("--metrics-recording-only")
                    .build()
                    .map_err(|e| anyhow!(e))?
            },
        };
        Ok(config)
    }
}

pub async fn get_device_metadata(device_id: &str) -> Result<DeviceMetadata> {
    let devices = GLOBAL_DEVICES.get()
        .ok_or_else(|| anyhow!("Device manager not initialized"))?;
    
    let manager = devices.read().await;
    manager.devices.get(device_id)
        .map(|device| device.metadata.clone())
        .ok_or_else(|| anyhow!("Device not found"))
}

pub async fn get_device_browser(device_id: &str) -> Result<Arc<EmulatedBrowser>> {
    let devices = GLOBAL_DEVICES.get()
        .ok_or_else(|| anyhow!("Device manager not initialized"))?;
    
    let manager = devices.read().await;
    manager.devices.get(device_id)
        .map(|device| Arc::new(device.browser.clone()))
        .ok_or_else(|| anyhow!("Device not found"))
}

// Публичный API для работы с устройствами
pub async fn initialize_emulation() -> Result<()> {

    info!("Инициализация эмуляции устройств...");

    let device_manager = Arc::new(RwLock::new(DeviceManager::new()));
    
    {
        let mut manager = device_manager.write().await;
        manager.create_ios_device("ios_device").await?;
        manager.create_android_device("android_device").await?;
    }
    
    GLOBAL_DEVICES.set(device_manager)
        .map_err(|_| anyhow!("Failed to set global devices"))?;

    Ok(())
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct WebKitFlags {
    pub enable_inspect: bool,
    pub enable_remote_debugging: bool,
    pub force_webkit_views: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct ChromeFlags {
    pub enable_automation: bool,
    pub disable_web_security: bool,
    pub ignore_certificate_errors: bool,
}