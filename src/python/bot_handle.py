import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from utils import ScreenRecorder, HumanBehavior
from tracer import TracerManager
from web_modules import GameCanvasHandler
from device_emulation import get_telegram_device_config
from bombie.bot_logic import WebAppLogic
from dotenv import load_dotenv
import os

# Загрузка переменных окружения
load_dotenv()

# Получение настроек из .env
ENABLE_SCREENSHOTS = os.getenv('ENABLE_SCREENSHOTS', 'false').lower() == 'true'
ENABLE_VIDEO = os.getenv('ENABLE_VIDEO', 'false').lower() == 'true'
ENABLE_TRACING = os.getenv('ENABLE_TRACING', 'false').lower() == 'true'
ENABLE_LOGGING = os.getenv('ENABLE_LOGGING', 'true').lower() == 'true'
ENABLE_HEADLESS = os.getenv('ENABLE_HEADLESS', 'false').lower() == 'true'

# Статические настройки
MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 5

# Размеры viewport и окна браузера
VIEWPORT_WIDTH = 412
VIEWPORT_HEIGHT = 815

class BotHandler:
    def __init__(self, webapp_url: str):
        self.webapp_url = webapp_url
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.device_config = get_telegram_device_config()
        self.tracer: Optional[TracerManager] = None
        self.recorder: Optional[ScreenRecorder] = None
        self.human: HumanBehavior = HumanBehavior()
        self.is_running = False
        self.reconnect_attempts = 0

        # Настройка логирования в зависимости от ENABLE_LOGGING
        if ENABLE_LOGGING:
            logger.add(
                "logs/bot_handler_{time}.log",
                rotation="1 hour",
                retention="7 days",
                level="DEBUG",
                backtrace=True,
                diagnose=True,
            )

    async def check_browser_installation(self):
        """Проверка установки браузера"""
        try:
            from playwright.async_api import async_playwright
            import os
            import sys
            import glob
            
            # Получаем путь к виртуальному окружению
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            playwright_cache = os.path.join(project_root, 'python_env', 'playwright-cache')
            
            # Создаем директорию для кэша если её нет
            os.makedirs(playwright_cache, exist_ok=True)
            
            # Устанавливаем переменную окружения для кэша Playwright
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = playwright_cache
            
            try:
                # Проверяем наличие браузера через glob
                browser_path = os.path.join(playwright_cache, 'chromium-*')
                if not glob.glob(browser_path):
                    raise Exception("Executable doesn't exist")
                    
                playwright = await async_playwright().start()
                await playwright.stop()
                logger.info(f"Браузер Playwright доступен в {playwright_cache}")
                return True
            except Exception as e:
                if "Executable doesn't exist" in str(e):
                    logger.warning("Браузеры Playwright не установлены, выполняем установку...")
                    
                    # Используем путь к Python из виртуального окружения
                    venv_python = os.path.join(project_root, 'python_env', 
                                                'bin' if not sys.platform.startswith('win') else 'Scripts',
                                                'python' + ('.exe' if sys.platform.startswith('win') else ''))
                    
                    process = subprocess.Popen(
                        [venv_python, '-m', 'playwright', 'install', 'chromium'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env={'PLAYWRIGHT_BROWSERS_PATH': playwright_cache}
                    )
                    stdout, stderr = process.communicate()
                    
                    if process.returncode == 0:
                        # Устанавливаем системные зависимости
                        deps_process = subprocess.Popen(
                            [venv_python, '-m', 'playwright', 'install-deps', 'chromium'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env={'PLAYWRIGHT_BROWSERS_PATH': playwright_cache}
                        )
                        deps_stdout, deps_stderr = deps_process.communicate()
                        
                        if deps_process.returncode == 0:
                            logger.info(f"Браузеры Playwright успешно установлены в {playwright_cache}")
                            return True
                        else:
                            logger.error(f"Ошибка установки зависимостей: {deps_stderr.decode()}")
                            return False
                    else:
                        logger.error(f"Ошибка установки браузеров: {stderr.decode()}")
                        return False
                else:
                    raise
        except Exception as e:
            logger.error(f"Ошибка при проверке браузера: {e}")
            return False

    async def setup_browser(self) -> bool:
        """Инициализация браузера и контекста"""
        try:
            # Сначала проверяем установку браузера
            if not await self.check_browser_installation():
                logger.error("Браузер Playwright не установлен или не настроен")
                return False

            self.playwright = await async_playwright().start()
            logger.debug("Playwright успешно инициализирован")
            
            # Запуск браузера с явным указанием размера окна
            self.browser = await self.playwright.chromium.launch(
                headless=ENABLE_HEADLESS,
                args=[
                    f'--window-size={VIEWPORT_WIDTH},{VIEWPORT_HEIGHT}',
                    '--force-device-scale-factor=1',
                    '--mute-audio',
                    '--hide-scrollbars',
                    '--window-position=0,0'
                ]
            )
            logger.info(f"Chromium браузер запущен в режиме отображения с размерами: {VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}")
    
            # Создание контекста с эмуляцией устройства
            self.context = await self.browser.new_context(
                viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                device_scale_factor=self.device_config['device_scale_factor'],
                user_agent=self.device_config['user_agent']
            )
            
            # Создание страницы
            self.page = await self.context.new_page()

            # Установка размера viewport
            await self.page.set_viewport_size({
                "width": VIEWPORT_WIDTH,
                "height": VIEWPORT_HEIGHT
            })
            
            logger.debug(f"Размеры viewport и окна браузера синхронизированы: {VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}")
            
            # Инициализация трейсера
            if ENABLE_TRACING:
                self.tracer = TracerManager(self.page, self.device_config)
            
            # Инициализация записи
            if ENABLE_SCREENSHOTS or ENABLE_VIDEO:
                self.recorder = ScreenRecorder(
                    enable_video=ENABLE_VIDEO,
                    enable_screenshots=ENABLE_SCREENSHOTS
                )
            
            logger.info("Браузер успешно инициализирован")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации браузера: {e}")
            return False

    async def _setup_webapp_event_handlers(self):
        """Настройка обработчиков событий WebApp"""
        await self.page.evaluate("""
            () => new Promise((resolve) => {
                const waitForWebApp = (retries = 0) => {
                    const tg = window.Telegram?.WebApp;
                    if (tg && tg.ready) {
                        // Сначала устаналиваем обработчики событий
                        const events = [
                            'themeChanged',
                            'viewportChanged',
                            'mainButtonClicked',
                            'backButtonClicked',
                            'settingsButtonClicked',
                            'invoiceClosed',
                            'popupClosed',
                            'qrTextReceived'
                        ];
                        
                        events.forEach(event => {
                            tg.onEvent(event, (data) => {
                                if (window.telegramTracker) {
                                    window.telegramTracker.logEvent({
                                        type: 'telegram_event',  // Изменили тип для различения
                                        event_name: event,
                                        data: data,
                                        timestamp: Date.now(),
                                        source: 'telegram_webapp'
                                    });
                                }
                            });
                        });

                        // Отдельно отслеживаем изменение основных параметров
                        const trackMainButton = () => {
                            if (tg.MainButton) {
                                window.telegramTracker.logEvent({
                                    type: 'telegram_state',
                                    component: 'MainButton',
                                    state: {
                                        isVisible: tg.MainButton.isVisible,
                                        text: tg.MainButton.text,
                                        color: tg.MainButton.color,
                                        textColor: tg.MainButton.textColor
                                    }
                                });
                            }
                        };

                        // Отслеживание BackButton
                        const trackBackButton = () => {
                            if (tg.BackButton) {
                                window.telegramTracker.logEvent({
                                    type: 'telegram_state',
                                    component: 'BackButton',
                                    state: {
                                        isVisible: tg.BackButton.isVisible
                                    }
                                });
                            }
                        };

                        // Регистрируем дополнительные обработчики
                        tg.onEvent('mainButtonClicked', trackMainButton);
                        tg.onEvent('backButtonClicked', trackBackButton);

                        // Теперь вызываем ready() и expand()
                        tg.ready();
                        tg.expand();
                        
                        resolve();
                    } else if (retries < 10) {
                        setTimeout(() => waitForWebApp(retries + 1), 100);
                    } else {
                        console.error('WebApp initialization timeout');
                        resolve();
                    }
                };
                
                waitForWebApp();
            });
        """)

    async def navigate_to_webapp(self) -> bool:
        """Навигация к WebApp"""
        MAX_RETRY_ATTEMPTS = 2
        retry_count = 0
        
        while retry_count <= MAX_RETRY_ATTEMPTS:
            try:
                # Модифицируем URL для установки версии 8.0
                webapp_url = self.webapp_url
                if 'tgWebAppVersion=' in webapp_url:
                    # Находим текущую версию в URL
                    version_start = webapp_url.find('tgWebAppVersion=') + len('tgWebAppVersion=')
                    version_end = webapp_url.find('&', version_start)
                    current_version = webapp_url[version_start:version_end] if version_end != -1 else webapp_url[version_start:]
                    
                    # Если версия не 8.0, заменяем её
                    if current_version != '8.0':
                        webapp_url = webapp_url.replace(
                            f'tgWebAppVersion={current_version}',
                            'tgWebAppVersion=8.0'
                        )
                        logger.info(f"Версия WebApp изменена с {current_version} на 8.0")
                
                logger.info(f"Переход по URL (попытка {retry_count + 1}/{MAX_RETRY_ATTEMPTS + 1}): {webapp_url}")
                
                # Переход по URL с обновленной версией
                response = await self.page.goto(
                    webapp_url,
                    wait_until='networkidle'
                )
                
                if not response or not response.ok:
                    logger.error(f"Ошибка загрузки страницы. Статус: {response.status if response else 'Нет ответа'}")
                    if retry_count < MAX_RETRY_ATTEMPTS:
                        retry_count += 1
                        logger.info(f"Повторная попытка через {RECONNECT_DELAY} секунд...")
                        await asyncio.sleep(RECONNECT_DELAY)
                        continue
                    return False

                # Инжектируем скрипт в head до загрузки других скриптов
                logger.debug("Инжектирование telegram-web-app.js в head...")
                await self.page.evaluate("""
                    () => new Promise((resolve, reject) => {
                        const script = document.createElement('script');
                        script.src = 'https://telegram.org/js/telegram-web-app.js';
                        
                        // Добавляем обработчик для отслеживания состояния загрузки
                        script.onload = () => {
                            console.log('WebApp script loaded');
                            if (window.Telegram?.WebApp) {
                                console.log('WebApp object available');
                                window.Telegram.WebApp.ready();
                                window.Telegram.WebApp.expand();
                                resolve();
                            } else {
                                reject(new Error('WebApp object not initialized'));
                            }
                        };
                        script.onerror = () => reject(new Error('Failed to load WebApp script'));
                        
                        // Вставляем скрипт в начало head
                        const head = document.getElementsByTagName('head')[0];
                        head.insertBefore(script, head.firstChild);
                    })
                """)
                logger.info("Скрипт WebApp успешно инжектирован")

                # Настройка обработчиков событий WebApp
                await self._setup_webapp_event_handlers()
                
                # Проверяем инициализацию и состоние WebApp
                init_status = await self.page.evaluate("""
                    () => {
                        const tg = window.Telegram?.WebApp;
                        return {
                            initialized: !!tg,
                            version: tg?.version,
                            platform: tg?.platform,
                            colorScheme: tg?.colorScheme,
                            themeParams: tg?.themeParams,
                            isExpanded: tg?.isExpanded,
                            viewportHeight: tg?.viewportHeight,
                            viewportStableHeight: tg?.viewportStableHeight
                        };
                    }
                """)
                
                logger.info(f"Статус инициализации WebApp: {init_status}")

                # Модуль для Bombie бота который для других ботов
                # может быть не валидным или требовать изменений
                # Работа с Canvas объектами 
                if init_status['initialized']:
                    try:
                        logger.info("Ожидание редиректа на игру...")
                        
                        # Ждем редирект с таймаутом
                        await self.page.wait_for_function(
                            "() => window.location.href.includes('games.pluto.vision')",
                            timeout=50000
                        )
                        logger.info(f"Редирект выполнен успешно: {self.page.url}")
                        
                        # Ждем загрузку страницы после редиректа
                        await self.page.wait_for_load_state('networkidle')
                        logger.info("Страница успешно загружена")
                        
                        # Инициализируем обработчик canvas только после полной загрузки
                        canvas_handler = GameCanvasHandler(self.page)
                        if not await canvas_handler.initialize():
                            logger.error("Не удалось инициализировать canvas")
                            return False
                            
                        logger.info("Canvas успешно инициализирован и готов к работе")
                        return True
                        
                    except Exception as e:
                        logger.error(f"Ошибка при ожидании редиректа или инициализации canvas: {e}")
                        return False

                return False  # Возвращаем False если WebApp не инициализирован

            except Exception as e:
                if "Timeout" in str(e):
                    if retry_count < MAX_RETRY_ATTEMPTS:
                        retry_count += 1
                        logger.warning(f"Таймаут при навигации (попытка {retry_count}/{MAX_RETRY_ATTEMPTS + 1})")
                        logger.info(f"Повторная попытка через {RECONNECT_DELAY} секунд...")
                        await asyncio.sleep(RECONNECT_DELAY)
                        continue
                    else:
                        logger.error(f"Превышено количество попыток навигации после таймаута: {e}")
                        return False
                elif "net::ERR_CERT_AUTHORITY_INVALID" in str(e) or "ERR_CONNECTION_CLOSED" in str(e):
                    logger.critical("💀 ПРОБЛЕМА С IP ИЛИ СЕССИЕЙ! ПРОВЕРЬТЕ СОЕДИНЕНИЕ И СМЕНИТЕ PROXY! 💀")
                    return False
                else:
                    logger.error(f"Ошибка на��игации: {e}")
                    return False

    async def check_connection(self) -> bool:
        """Проверка соединения и попытка переподключения"""
        try:
            if self.page.is_closed():
                # Проверяем, был ли браузер закрыт вручную
                if self.browser.is_connected() == False:
                    logger.info("Браузер был закрыт вручную")
                    return False
                logger.warning("Страница закрыта, требуется переподключение")
                return await self.try_reconnect()
                
            # Проверка доступности WebApp
            # logger.debug("Проверка доступности WebApp...")
            is_available = await self.page.evaluate(
                "() => !!window.Telegram?.WebApp"
            )
            
            if not is_available:
                logger.error("WebApp недоступен, попытка переподключения")
                return await self.try_reconnect()
                
            # logger.debug("Соединение активно")
            return True
            
        except Exception as e:
            # Проверяем специфические ошибки закрытия браузера
            if "Browser closed" in str(e) or "Target closed" in str(e):
                logger.info("Браузер был закрыт вручную")
                return False
            logger.error(f"Ошибка проверки соединения: {e}")
            return await self.try_reconnect()

    async def try_reconnect(self) -> bool:
        """Попытка переподключения"""
        if self.reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            logger.error(f"Превышено максимальное количество попыток переподключения ({MAX_RECONNECT_ATTEMPTS})")
            self.is_running = False
            return False
            
        self.reconnect_attempts += 1
        logger.info(f"Попытка переподключения {self.reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS}")
        
        logger.debug(f"Ожидание {RECONNECT_DELAY} секунд перед переподключением...")
        await asyncio.sleep(RECONNECT_DELAY)
        
        try:
            logger.debug("Очистка текущей сессии...")
            await self.cleanup(full=False)
            
            logger.debug("Попытка переинициализации браузера...")
            if await self.setup_browser():
                logger.debug("Попытка повторной навигации...")
                if await self.navigate_to_webapp():
                    logger.info("Переподключение успешно выполнено")
                    self.reconnect_attempts = 0
                    return True
                else:
                    logger.error("Ошибка навигации при переподключении")
            else:
                logger.error("Ошибка инициализации браузера при переподключении")
                
        except Exception as e:
            logger.error(f"Ошибка во время переподключения: {e}")
            
        return False

    async def cleanup(self, full: bool = True):
        """Очистка ресурсов"""
        try:
            if self.tracer:
                await self.tracer.stop_tracing()
                
            if self.context:
                await self.context.close()
                
            if self.browser:
                await self.browser.close()
                
            if full and self.playwright:
                await self.playwright.stop()
                
        except Exception as e:
            logger.error(f"Ошибка при очистке ресурсов: {e}")

    async def run(self) -> bool:
        """Основной метод работы"""
        try:
            logger.info("Запуск обработчика WebApp")
            
            # Инициализация
            logger.debug("Инициализация браузера...")
            if not await self.setup_browser():
                logger.error("Не удалось инициализировать браузер")
                return False
                
            self.is_running = True
            
            # Запуск трейсинга
            if ENABLE_TRACING:
                logger.debug("Запуск трейсинга...")
                await self.tracer.start_tracing()
            
            # Навигация к WebApp
            logger.debug("Навигация к WebApp...")
            if not await self.navigate_to_webapp():
                logger.error("Не удалось выполнить навигацию к WebApp")
                return False

            # Инициализация и запуск логики WebApp
            logger.info("Запуск основной логики действий бота")
            webapp_logic = WebAppLogic(self.page)
            logic_task = asyncio.create_task(webapp_logic.start_logic())
            
            # Основной цикл работы
            while self.is_running:
                try:
                    if not await self.check_connection():
                        # Проверяем, был ли браузер закрыт вручную
                        if self.browser.is_connected() == False:
                            logger.info("Браузер был закрыт вручную - успешное завершение")
                            return True
                        logger.warning("Потеряно соединение, завершение работы")
                        break
                    
                    # Имитация человеческого поведения
                    delay = await self.human.random_delay()
                                        
                    # Создание скриншота
                    if self.recorder and ENABLE_SCREENSHOTS:
                        logger.debug("Создание скриншота...")
                        await self.recorder.take_screenshot(
                            self.page,
                            "monitoring"
                        )
                        
                except Exception as e:
                    # Проверяем специфические ошибки, связанные с закрытием браузера
                    if "Browser closed" in str(e) or "Target closed" in str(e):
                        logger.info("Браузер был закрыт вручную - успешное завершение")
                        return True
                    raise
            
            # Останавливаем логику WebApp
            webapp_logic.is_running = False
            await logic_task
            
            logger.info("Завершение работы обработчика")
            return True
            
        except Exception as e:
            logger.error(f"Критическая ошибка в обработчике: {e}")
            return False
            
        finally:
            logger.debug("Очистка ресурсов...")
            await self.cleanup()

async def handle_webapp(webapp_url: str) -> bool:
    """Точка входа для запуска обработчика"""
    try:
        handler = BotHandler(webapp_url)
        return await handler.run()
        
    except Exception as e:
        logger.error(f"Ошибка запуска обработчика: {e}")
        return False