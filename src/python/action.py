from loguru import logger
import asyncio
import os
import traceback
from telethon import TelegramClient, types
import sys
from utils import HumanBehavior
from dotenv import load_dotenv
from login import TelegramLogin
import json
from telethon.tl.functions.messages import RequestWebViewRequest
from telethon.tl.types import DataJSON
from telethon.tl.types import InputUser
from urllib.parse import urlparse
from bot_handle import handle_webapp

# Загрузка переменных окружения
load_dotenv()

# Получение настройки логирования из .env
ENABLE_LOGGING = os.getenv('ENABLE_LOGGING', 'true').lower() == 'true'

class TelegramMiniAppAutomation:
    def __init__(self, client: TelegramClient, app_url: str, device_config: dict, bot_metadata: dict = None, webapp_data: dict = None):
        self.client = client
        self.app_url = app_url
        self.device_config = device_config
        self.behavior = HumanBehavior()
        self.setup_logging()
        self._cleanup_lock = asyncio.Lock()
        self._is_shutting_down = False
        self.init_data = None
        self.init_params = None
        self.verified = False
        self.bot_metadata = bot_metadata
        self.webapp_data = webapp_data
        self.bot_peer = None
        self.bot_input_user = None

    def setup_logging(self):
        """Настройка логирования"""
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO",
        )
        
        # Добавляем файловое логирование только если оно включено
        if ENABLE_LOGGING:
            logger.add(
                "logs/miniapp_automation_{time}.log",
                rotation="1 day",
                retention="7 days",
                level="DEBUG",
            )

    async def initialize_webapp(self) -> bool:
        """Инициализация WebApp через MTProto"""
        try:
            logger.info("Начало инициализации WebApp")
            
            if not self.bot_metadata or not self.webapp_data:
                logger.error("Отсутствуют метаданные бота или данные WebApp")
                return False

            # Проверяем и конвертируем данные из строки в dict если необходимо
            if isinstance(self.bot_metadata, str):
                try:
                    self.bot_metadata = json.loads(self.bot_metadata)
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка декодирования bot_metadata JSON: {e}")
                    return False

            # Получаем необходимые сущности
            try:
                self.bot_peer = await self.client.get_input_entity(self.bot_metadata.get('username'))
                logger.debug(f"Получен bot_peer: {self.bot_peer}")
                
                bot_input_user = types.InputUser(
                    user_id=self.bot_metadata.get('bot_id'),
                    access_hash=self.bot_metadata.get('access_hash')
                )
                logger.debug(f"Создан InputUser для бота: {bot_input_user}")
                
            except Exception as e:
                logger.error(f"Ошибка получения сущностей: {e}")
                return False

            # Валидируем и подготавливаем параметры темы
            theme_params = self._validate_theme_params(self.webapp_data.get('theme_params', {}))
            platform = self.webapp_data.get('platform', 'android')
            
            logger.info(f"Используем платформу: {platform}")
            logger.info(f"Валидированные параметры темы: {theme_params}")

            # Выполняем запрос WebView
            try:
                result = await self.client(RequestWebViewRequest(
                    peer=self.bot_peer,
                    bot=bot_input_user,
                    url=self.app_url,
                    platform=platform,
                    from_bot_menu=False,
                    theme_params=DataJSON(data=json.dumps(theme_params))
                ))
                logger.info(f"Запрос WebView выполнен успешно")
                logger.info(f"Получен WebView URL: {result.url}")
                
                # Сохраняем только URL для дальнейшего использования
                self.app_url = result.url
                
                # Проверяем корректность полученного URL
                if not self._validate_webapp_url(result.url):
                    logger.error("Получен некорректный WebView URL")
                    return False
                    
                return True

            except Exception as e:
                logger.error(f"Ошибка запроса WebView: {e}")
                logger.debug(f"Stacktrace: {traceback.format_exc()}")
                return False

        except Exception as e:
            logger.error(f"Критическая ошибка инициализации WebApp: {e}")
            logger.debug(f"Stacktrace: {traceback.format_exc()}")
            return False

    def _validate_theme_params(self, theme_params: dict) -> dict:
        """Валидация параметров темы"""
        default_theme_params = {
            "bg_color": "#ffffff",
            "text_color": "#000000",
            "hint_color": "#999999",
            "link_color": "#2481cc",
            "button_color": "#2481cc",
            "button_text_color": "#ffffff",
            "secondary_bg_color": "#f0f0f0"
        }
        
        if isinstance(theme_params, str):
            try:
                theme_params = json.loads(theme_params)
            except json.JSONDecodeError:
                return default_theme_params
                
        validated_params = {}
        for key, default_value in default_theme_params.items():
            value = theme_params.get(key, default_value)
            if isinstance(value, str) and value.startswith('#') and len(value) in [4, 7]:
                validated_params[key] = value
            else:
                validated_params[key] = default_value
                
        return validated_params

    def _validate_webapp_url(self, url: str) -> bool:
        """Валидация URL WebApp согласно документации Telegram"""
        try:
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                logger.error("URL не содержит scheme или netloc")
                return False
            
            # Получаем параметры из fragment
            fragment_params = {}
            if parsed.fragment:
                fragment_parts = parsed.fragment.split('&')
                for part in fragment_parts:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        fragment_params[key] = value

            # Проверяем обязательные параметры
            required_params = ['tgWebAppData', 'tgWebAppVersion', 'tgWebAppPlatform']
            for param in required_params:
                if param not in fragment_params:
                    logger.error(f"Отсутствует обязательный параметр: {param}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Ошибка валидации URL: {e}")
            return False

    async def navigate_to_app(self):
        """Обновленная навигация к приложению"""
        try:
            if not await self.initialize_webapp():
                return False

            logger.info("WebApp успешно инициализирован и готов к работе")
            return True

        except Exception as e:
            logger.error(f"Ошибка при навигации: {e}")
            return False

async def initialize_automation() -> bool:
    """Точка входа для вызова из Rust"""
    tracer = None
    automation = None
    login = None
    try:
        # Загружаем переменные окружения
        load_dotenv()
        
        # Получаем необходимые параметры из .env
        api_id = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")
        phone = os.getenv("TELEGRAM_PHONE")
        
        if not all([api_id, api_hash, phone]):
            logger.error("Отсутствуют необходимые переменные окружения")
            return False
            
        try:
            logger.info("Создание объекта TelegramLogin")
            login = TelegramLogin(
                api_id=int(api_id),
                api_hash=api_hash,
                phone=phone
            )
            
            # Выполняем подключение
            success, url, device_config, bot_metadata, webapp_data = await login.connect()
            
            if success:
                logger.info("Логин успешно выполнен")
                if url:
                    logger.info(f"Получен URL: {url}")
                    client = login.client
                    
                    # Создаем объект автоматизации
                    automation = TelegramMiniAppAutomation(
                        client=client,
                        app_url=url,
                        device_config=device_config,
                        bot_metadata=bot_metadata,
                        webapp_data=webapp_data,
                    )
                    
                    # Получаем WebView URL через navigate_to_app
                    if await automation.navigate_to_app():
                        # Используем automation.app_url вместо исходного url
                        webapp_url = automation.app_url
                        logger.info(f"Запуск обработчика WebApp с URL: {webapp_url}")
                        
                        try:
                            # Передаем WebView URL в handle_webapp
                            bot_task = asyncio.create_task(handle_webapp(webapp_url))
                            result = await bot_task
                            
                            if result:
                                logger.info("Обработчик WebApp успешно завершил работу")
                            else:
                                logger.error("Обработчик WebApp завершился с ошибкой")
                                
                            return result
                                
                        except asyncio.CancelledError:
                            logger.warning("Задача обработчика WebApp была отменена")
                            return False
                        except Exception as e:
                            logger.error(f"Ошибка при выполнении задачи обработчика: {e}")
                            return False
                    
                    logger.error("Не удалось получить WebView URL")
                    return False

                else:
                    logger.warning("URL не найден")
                    client = login.client
                    if bot_metadata:
                        logger.info(f"Получены метаданные бота: {bot_metadata}")
                    if webapp_data:
                        logger.info(f"Получены данные WebApp: {webapp_data}")
                    
                    if not client:
                        logger.error("Не удалось получить клиент")
                        return False

                    logger.info("Создание объекта TelegramMiniAppAutomation")
                    automation = TelegramMiniAppAutomation(
                        client=client,
                        app_url=url,
                        device_config=device_config,
                        bot_metadata=bot_metadata,
                        webapp_data=webapp_data,
                    )
                    
                    # Навигация к приложению
                    await automation.navigate_to_app()

                    if success and url:
                        logger.info(f"Запуск обработчика WebApp с URL: {url}")
                        
                        # Создаем и запускаем задачу
                        try:
                            # Запускаем обработчик как отдельную задачу
                            bot_task = asyncio.create_task(handle_webapp(url))
                            
                            # Ожидаем завершения задачи
                            result = await bot_task
                            
                            if result:
                                logger.info("Обработчик WebApp успешно завершил работу")
                            else:
                                logger.error("Обработчик WebApp завершился с ошибкой")
                                
                            return result
                                
                        except asyncio.CancelledError:
                            logger.warning("Задача обработчика WebApp была отменена")
                            return False
                        except Exception as e:
                            logger.error(f"Ошибка при выполнении задачи обработчика: {e}")
                            return False
                    
                    logger.error("URL не получен, обработчик не запущен")
                    return False
                
            else:
                logger.error("Ошибка входа в Telegram")
                return False
                
        except Exception as e:
            logger.error(f"Критическая ошибка инициализации: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Критическая ошибка автоматизации: {e}")
        return False
        
    finally:
        # Корректное закрытие ресурсов
        try:
            if login:
                logger.debug("Очистка ресурсов логина")
                await login.cleanup()
        except Exception as e:
            logger.error(f"Ошибка при закрытии ресурсов: {e}")

if __name__ == "__main__":
    # Для тестирования
    async def test():
        from telethon import TelegramClient
        client = TelegramClient('test_session', '123', 'abc')
        await initialize_automation()
    
    asyncio.run(test())