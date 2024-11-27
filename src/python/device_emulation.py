import random
from dataclasses import dataclass
from typing import Dict, List, Optional
from loguru import logger

@dataclass
class AndroidDevice:
    """Расширенный класс для хранения данных об эмулируемом Android-устройстве"""
    # Параметры для Telegram API
    device_model: str
    system_version: str
    app_version: str
    lang_code: str
    system_lang_code: str
    device_info: Dict[str, str]
    
    # WebView специфичные параметры
    user_agent: str
    viewport_width: int
    viewport_height: int
    device_scale_factor: float
    
    # Telegram WebApp параметры
    tg_webapp_platform: str
    tg_webapp_theme: str
    tg_webapp_version: str
    tg_webapp_start_param: str


class AndroidDeviceEmulator:
    """Расширенный эмулятор Android-устройств с WebView параметрами"""
    def __init__(self):
        self.devices = [
            AndroidDevice(
                # Telegram API параметры
                device_model="Pixel 7 Pro",
                system_version="Android 14",
                app_version="10.6.1",
                lang_code="ru",
                system_lang_code="ru-RU",
                device_info={
                    "brand": "Google",
                    "model": "GP4BC",
                    "sdk": "34",
                    "hardware": "tensor"
                },
                # WebView параметры реального Pixel 7 Pro
                user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
                viewport_width=412,
                viewport_height=915,
                device_scale_factor=3.5,
                
                # Telegram WebApp параметры
                tg_webapp_platform="android",
                tg_webapp_theme="light",
                tg_webapp_version="7.10",
                tg_webapp_start_param=""
            ),
            AndroidDevice(
                # Telegram API параметры
                device_model="Galaxy S23 Ultra",
                system_version="Android 14",
                app_version="10.5.0",
                lang_code="ru",
                system_lang_code="ru-RU",
                device_info={
                    "brand": "samsung",
                    "model": "SM-S918B",
                    "sdk": "34",
                    "hardware": "qcom"
                },
                # WebView параметры реального S23 Ultra
                user_agent="Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
                viewport_width=384,
                viewport_height=854,
                device_scale_factor=3.75,
                
                # Telegram WebApp параметры
                tg_webapp_platform="android",
                tg_webapp_theme="light",
                tg_webapp_version="7.10",
                tg_webapp_start_param=""
            ),
            AndroidDevice(
                # Telegram API параметры
                device_model="OnePlus 11",
                system_version="Android 14",
                app_version="10.4.2",
                lang_code="ru",
                system_lang_code="ru-RU",
                device_info={
                    "brand": "OnePlus",
                    "model": "CPH2449",
                    "sdk": "34",
                    "hardware": "qcom"
                },
                # WebView параметры реального OnePlus 11
                user_agent="Mozilla/5.0 (Linux; Android 14; CPH2449) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
                viewport_width=412,
                viewport_height=919,
                device_scale_factor=3.0,
                
                # Telegram WebApp параметры
                tg_webapp_platform="android",
                tg_webapp_theme="light",
                tg_webapp_version="7.10",
                tg_webapp_start_param=""
            )
        ]
        self.selected_device = None

    def get_random_device(self) -> AndroidDevice:
        """Возвращает случайное устройство и сохраняет его для последующего использования"""
        self.selected_device = random.choice(self.devices)
        logger.info(f"Выбрано устройство: {self.selected_device.device_model}")
        return self.selected_device

def get_telegram_device_config() -> Dict[str, str]:
    """Возвращает конфигурацию для TelegramClient через эмулятор"""
    emulator = AndroidDeviceEmulator()
    device = emulator.get_random_device()
    
    return {
        # Параметры для TelegramClient
        "device_model": device.device_model,
        "system_version": device.system_version,
        "app_version": device.app_version,
        "lang_code": device.lang_code,
        "system_lang_code": device.system_lang_code,
        "user_agent": device.user_agent,
        
        # Параметры для WebApp
        "viewport": {
            "width": device.viewport_width,
            "height": device.viewport_height
        },
        "device_scale_factor": device.device_scale_factor,
        
        # Параметры Telegram WebApp
        "telegram_webapp": {
            "platform": device.tg_webapp_platform,
            "theme": device.tg_webapp_theme,
            "start_param": device.tg_webapp_start_param
        }
    }