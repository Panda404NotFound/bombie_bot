import os
import sys
import asyncio
from pathlib import Path
from typing import Optional, Tuple, Union, List, Dict, Any
from telethon import TelegramClient, events, functions
from telethon.tl.types import Message
from telethon.errors import SessionPasswordNeededError, AuthKeyUnregisteredError
from telethon.tl.custom.button import Button
from loguru import logger
from dotenv import load_dotenv
import getpass
import signal
from datetime import datetime
import json
import time

class TelegramLogin:
    def __init__(self, api_id: int, api_hash: str, phone: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_dir = Path(".py_session")
        self.session_file = self.session_dir / f"{phone.replace('+', '')}.session"
        self.client: Optional[TelegramClient] = None
        self.device_config = None

    async def ensure_session_directory(self):
        """Создание директории для сессий"""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Проверена директория сессий: {self.session_dir}")

    async def initialize_client(self) -> TelegramClient:
        """Инициализация клиента Telegram"""
        from device_emulation import get_telegram_device_config 
               
        self.device_config = get_telegram_device_config()
        
        client = TelegramClient(
            str(self.session_file),
            self.api_id,
            self.api_hash,
            device_model=self.device_config["device_model"],
            system_version=self.device_config["system_version"],
            app_version=self.device_config["app_version"],
            lang_code=self.device_config["lang_code"]
        )
        
        logger.info(f"Инициализация клиента с устройством: {self.device_config['device_model']}")
        return client

    async def handle_2fa(self, client: TelegramClient) -> bool:
        """Обработка двухфакторной аутентификации"""
        try:
            logger.info("Требуется 2FA")
            for _ in range(3):  # Даем 3 попытки ввода 2FA
                try:
                    password = getpass.getpass("Введите пароль 2FA: ")
                    await client.sign_in(password=password)
                    logger.info("2FA авторизация успешна")
                    return True
                except Exception as e:
                    logger.error(f"Ошибка 2FA: {e}")
                    continue  # Продолжаем попытки ввода 2FA
            
            # Если все попытки 2FA неудачны, очищаем сессию и начинаем заново
            logger.warning("Все попытки 2FA неудачны, очищаем сессию")
            await client.disconnect()
            if self.session_file.exists():
                self.session_file.unlink()
            
            # Создаем новый клиент и начинаем процесс входа заново
            self.client = await self.initialize_client()
            await self.client.connect()
            return await self.sign_in(self.client)
            
        except Exception as e:
            logger.error(f"Критическая ошибка 2FA: {e}")
            # В случае критической ошибки также очищаем сессию
            await client.disconnect()
            if self.session_file.exists():
                self.session_file.unlink()
            return False

    async def sign_in(self, client: TelegramClient) -> bool:
        """Процесс входа в аккаунт"""
        try:
            if not await client.is_user_authorized():
                logger.info("Начинаем процесс входа...")
                
                # Запрашиваем код
                phone = await client.send_code_request(self.phone)
                
                # Ждем ввод кода
                for attempt in range(3):
                    try:
                        code = getpass.getpass(f"Введите код подтверждения (попытка {attempt + 1}/3): ")
                        await client.sign_in(self.phone, code, phone_code_hash=phone.phone_code_hash)
                        logger.info("Успешный вход в аккаунт")
                        return True
                    except SessionPasswordNeededError:
                        return await self.handle_2fa(client)
                    except Exception as e:
                        logger.error(f"Ошибка входа: {e}")
                        if attempt == 2:
                            return False
            else:
                logger.info("Уже авторизован")
                return True
                
        except Exception as e:
            logger.error(f"Критическая ошибка входа: {e}")
            return False

    async def find_bot_url(self, client: TelegramClient) -> Tuple[Optional[str], Dict[str, Any]]:
        """Поиск URL бота с учетом приоритетов"""
        try:
            bot_name = os.getenv("TELEGRAM_BOT_NAME")
            found_url = None
            bot_metadata = None

            # Ищем бота в диалогах
            async for dialog in client.iter_dialogs():
                if dialog.name == bot_name:
                    logger.info(f"Найден бот: {bot_name}")
                    found_url, bot_metadata = await self.process_bot_chat(client, dialog)
                    break
            
            # Если бот не найден в диалогах, пробуем найти по username
            if not found_url:
                bot_username = os.getenv("BOT_URL", "").strip()
                if bot_username:
                    if bot_username.startswith('@'):
                        bot_username = bot_username[1:]
                    logger.info(f"Пытаемся найти бота по username: {bot_username}")
                    
                    try:
                        bot_entity = await client.get_entity(bot_username)
                        logger.info(f"Бот найден: {bot_entity.username}")
                        
                        logger.info("Отправляем команду /start")
                        await client.send_message(bot_entity, "/start")
                        await asyncio.sleep(2)
                        
                        # Получаем диалог с ботом
                        async for dialog in client.iter_dialogs():
                            if dialog.entity.id == bot_entity.id:
                                logger.info("Обрабатываем новый диалог с ботом")
                                found_url, bot_metadata = await self.process_bot_chat(client, dialog)
                                break
                    except Exception as e:
                        logger.error(f"Ошибка при инициализации бота: {e}")

            # Проверяем результаты и приоритеты
            env_bot_url = os.getenv("TELEGRAM_BOT_URL", "").strip()
            
            if env_bot_url:
                logger.info(f"Используем URL из .env: {env_bot_url}")
                return env_bot_url, bot_metadata
            elif found_url:
                logger.info(f"Используем найденный URL: {found_url}")
                return found_url, bot_metadata
            else:
                error_msg = f"Бот {bot_name} не найден в диалогах и нет доступных URL"
                logger.error(error_msg)
                sys.exit(f"КРИТИЧЕСКАЯ ОШИБКА: {error_msg}")

        except Exception as e:
            error_msg = f"Ошибка поиска URL: {e}"
            logger.error(error_msg)
            sys.exit(f"КРИТИЧЕСКАЯ ОШИБКА: {error_msg}")

    async def get_bot_metadata(self, entity) -> Dict[str, Any]:
        """Получение метаданных бота"""
        try:
            return {
                'bot_id': entity.id,
                'access_hash': entity.access_hash,
                'username': entity.username,
                'bot_info_version': getattr(entity, 'bot_info_version', None)
            }
        except Exception as e:
            logger.error(f"Ошибка получения метаданных бота: {e}")
            return {}

    async def prepare_webapp_data(self, client: TelegramClient, bot_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Подготовка данных для инициализации WebApp"""
        try:
            user = await client.get_me()
            return {
                'user': {
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'username': user.username,
                    'language_code': self.device_config.get('lang_code', 'ru')
                },
                'auth_date': int(time.time()),
                'bot': bot_metadata,
                'platform': self.device_config.get('telegram_webapp', {}).get('platform', 'desktop'),
                'theme_params': self.device_config.get('telegram_webapp', {}).get('theme', {})
            }
        except Exception as e:
            logger.error(f"Ошибка подготовки данных WebApp: {e}")
            return {}

    async def process_bot_chat(self, client: TelegramClient, dialog) -> Tuple[Optional[str], Dict[str, Any]]:
        """Обработка чата бота для поиска URL и получения метаданных"""
        try:
            bot_entity = await client.get_entity(dialog.entity)
            metadata = await self.get_bot_metadata(bot_entity)
            url = await self._find_bot_url_internal(client, dialog)
            logger.debug(f"Найден URL бота: {url}, метаданные бота: {metadata}, диалог: {dialog}")
            return url, metadata
        except Exception as e:
            logger.error(f"Ошибка обработки чата бота: {e}")
            return None, {}

    async def _find_bot_url_internal(self, client: TelegramClient, dialog) -> Optional[str]:
        """Внутренний метод для поиска URL бота"""
        try:
            # Проверяем наличие сообщений
            messages_count = 0
            async for _ in client.iter_messages(dialog, limit=1):
                messages_count += 1

            # 1. Поиск URL в текущих сообщениях
            if messages_count > 0:
                logger.info("Найдены существующие сообщения, ищем URL...")
                url_or_button = await self.find_button_in_messages(client, dialog)
                found_button = None  # Сохраняем найденную обычную кнопку
                
                if isinstance(url_or_button, str):  # Прямая ссылка
                    logger.info(f"Найдена прмая ссылка: {url_or_button}")
                    if self._check_button_text(url_or_button, os.getenv("TELEGRAM_LAUNCH_BUTTON_TEXT")):
                        return url_or_button
                    else:
                        logger.info("Найденная ссылка не содержит целевой текст, продолжаем поиск")
                elif url_or_button:  # Кнопка или сообщение
                    logger.info("Найдена кнопка или сообщение, обрабатываем...")
                    try:
                        launch_button_text = os.getenv("TELEGRAM_LAUNCH_BUTTON_TEXT")
                        
                        # Сохраняем обычную кнопку, если она найдена
                        if hasattr(url_or_button, 'text') and not hasattr(url_or_button, 'url'):
                            found_button = url_or_button
                        
                        # Проверяем тип кнопки
                        if hasattr(url_or_button, 'callback_data'):  # Inline кнопка
                            logger.info("Обрабатываем inline кнопку")
                            await url_or_button.click()
                            await asyncio.sleep(2)
                            async for message in client.iter_messages(dialog, limit=1):
                                if url := await self.extract_url_from_message(message):
                                    if self._check_button_text(url, launch_button_text):
                                        return url
                                    
                        # Проверяем обычную копку клавиатуры
                        elif hasattr(url_or_button, 'text') and hasattr(url_or_button, 'button'):  
                            button_text = url_or_button.text
                            if launch_button_text.lower() in button_text.lower():
                                logger.info(f"Отправляем текст клавиатурной кнопки: {button_text}")
                                await client.send_message(dialog, button_text)
                                await asyncio.sleep(2)
                                async for message in client.iter_messages(dialog, limit=1):
                                    if url := await self.extract_url_from_message(message):
                                        if self._check_button_text(url, launch_button_text):
                                            logger.info(f"Получена подходящая ссылка: {url}")
                                            return url
                                        else:
                                            logger.info("Полученная ссылка не содержит целевой текст, продолжаем поиск")
                        # Обрабатываем текстовое сообщение
                        elif hasattr(url_or_button, 'text'):
                            message_text = url_or_button.text
                            if launch_button_text.lower() in message_text.lower():
                                logger.info(f"Найден целевой текст в сообщении, ищем URL")
                                if url := await self.extract_url_from_message(url_or_button):
                                    logger.info(f"Найдена ссылка в сообщении: {url}")
                                    return url
                                else:
                                    logger.info("URL в сообщении не найден, продолжаем поиск")
                        else:
                            logger.warning("Найденный элемент не является кнопкой или сообщением")
                        
                        # Если ни одна проверка не дала результата и у нас есть сохраненная обычная кнопка
                        if found_button and hasattr(found_button, 'text'):
                            button_text = found_button.text
                            logger.info(f"Пробуем отправить текст обычной кнопки как последний вариант: {button_text}")
                            await client.send_message(dialog, button_text)
                            await asyncio.sleep(2)
                            async for message in client.iter_messages(dialog, limit=1):
                                if url := await self.extract_url_from_message(message):
                                    return url
                                
                    except Exception as e:
                        logger.error(f"Ошибка при обработке кнопк/сообщения: {e}")

            # Если URL не найден, пробуем отправить /start
            logger.info("URL не найден, отправляем /start")
            await client.send_message(dialog, "/start")
            await asyncio.sleep(3)  # Ждем ответа
            
            # Повторяем поиск после /start
            url_or_button = await self.find_button_in_messages(client, dialog)
            if isinstance(url_or_button, str):
                return url_or_button
            elif url_or_button:
                if hasattr(url_or_button, 'text') and hasattr(url_or_button, 'button'):
                    # Если это клавиатурная кнопка
                    button_text = url_or_button.text
                    logger.info(f"Отправляем текст клавиатурной кнопки: {button_text}")
                    await client.send_message(dialog, button_text)
                else:
                    logger.info("Обрабатываем найденный элемент")
                    if hasattr(url_or_button, 'click'):
                        await url_or_button.click()
                
                await asyncio.sleep(2)
                async for message in client.iter_messages(dialog, limit=1):
                    if url := await self.extract_url_from_message(message):
                        return url

            logger.warning("URL не найден после всех попыток")
            return None

        except Exception as e:
            logger.error(f"Ошибка обработки чата бота: {e}")
            return None

    async def find_button_in_messages(self, client: TelegramClient, dialog) -> Union[str, Button, None]:
        """Поиск кнопки или URL с заданным текстом"""
        try:
            launch_button_text = os.getenv("TELEGRAM_LAUNCH_BUTTON_TEXT")
            logger.info(f"Ищем кнопку/ссылку с текстом: {launch_button_text}")
            
            async for message in client.iter_messages(dialog, limit=20):
                logger.debug(f"Анализ сообщения: {message}")

                # 1. Проверяем title сообщения (если есть)
                if hasattr(message, 'title') and message.title:
                    if self._check_button_text(message.title, launch_button_text):
                        logger.info(f"Найден текст в заголовке: {message.title}")
                        return message

                # 2. Проверяем текст сообщения
                if message.text:
                    if self._check_button_text(message.text, launch_button_text):
                        logger.info(f"Найден текст в сообщении: {message.text}")
                        return message

                    # Проверяем URL в тексте
                    urls = self.extract_urls_from_text(message.text)
                    for url in urls:
                        if launch_button_text.lower() in url.lower():
                            logger.info(f"Найден URL  тексте сообщения: {url}")
                            return url

                # 3. Проверяем игровые сообщения
                if hasattr(message, 'game') and message.game:
                    if hasattr(message.game, 'title') and self._check_button_text(message.game.title, launch_button_text):
                        logger.info(f"Найдена игровая кнопка: {message.game.title}")
                        return message.game
                    if hasattr(message.game, 'short_name') and self._check_button_text(message.game.short_name, launch_button_text):
                        logger.info(f"Найдена игровая кнопка (short_name): {message.game.short_name}")
                        return message.game

                # 4. Проверяем медиа-заголовки
                if message.media and hasattr(message.media, 'title'):
                    if self._check_button_text(message.media.title, launch_button_text):
                        logger.info(f"Найден текст в медиа: {message.media.title}")
                        return message

                # 5. Проверяем inline кнопки и разметку
                if message.reply_markup:
                    if hasattr(message.reply_markup, 'rows'):
                        for row in message.reply_markup.rows:
                            for button in row.buttons:
                                # Логируем все найденные кнопки для отладки
                                logger.debug(f"Проверка кнопки: {button}")
                                
                                if self._check_button_text(button.text, launch_button_text):
                                    # URL-кнопка
                                    if hasattr(button, 'url'):
                                        logger.info(f"Найдена URL-кнопка: {button.url}")
                                        return button.url
                                    # Игровая кнопка
                                    if hasattr(button, 'game'):
                                        logger.info(f"Найдена игровая инлайн-кнопка: {button.text}")
                                        return button
                                    # Callback-кнопка
                                    if hasattr(button, 'callback_data'):
                                        logger.info(f"Найдена callback-кнопка: {button.text}")
                                        return button
                                    # Обычная кнопка
                                    logger.info(f"Найдена обычная кнопка: {button.text}")
                                    return button

                # 6. Проверяем нижние кнопки клавиатуры (keyboard buttons)
                if hasattr(message, 'keyboard') and message.keyboard:
                    for row in message.keyboard.rows:
                        for button in row.buttons:
                            if self._check_button_text(button.text, launch_button_text):
                                logger.info(f"Найдена клавиатурная кнопка: {button.text}")
                                return button

            logger.warning(f"Кнопка/ссылка с текстом '{launch_button_text}' не найдена")
            return None

        except Exception as e:
            logger.error(f"Ошибка поиска кнопки/ссылки: {e}")
            return None

    async def extract_url_from_message(self, message: Message) -> Optional[str]:
        """Извлечение URL из сообщения"""
        try:
            launch_button_text = os.getenv("TELEGRAM_LAUNCH_BUTTON_TEXT")
            
            # Проверяем, является ли объект кнопкой клавиатуры
            if hasattr(message, 'button'):
                return None  # У клавиатурных кнопок нет URL
            
            # Проверяем текст сообщения
            if hasattr(message, 'text') and message.text:
                urls = self.extract_urls_from_text(message.text)
                if urls:
                    url = urls[0]
                    if self._check_button_text(url, launch_button_text):
                        return url
                    else:
                        logger.info(f"Найденная ссылка не содержит целевой текст: {url}")
                        return None
                    
            # Проверяем entities только если они есть
            if hasattr(message, 'entities') and message.entities:
                for entity in message.entities:
                    if hasattr(entity, 'url') and entity.url:
                        url = entity.url
                        if self._check_button_text(url, launch_button_text):
                            return url
                        else:
                            logger.info(f"Найдення ссылка в entity не содержит целевой текст: {url}")
                            return None

            # Проверяем разметку сообщения
            if hasattr(message, 'reply_markup') and message.reply_markup:
                if hasattr(message.reply_markup, 'rows'):
                    for row in message.reply_markup.rows:
                        for button in row.buttons:
                            if hasattr(button, 'url'):
                                url = button.url
                                if self._check_button_text(url, launch_button_text):
                                    return url
                                else:
                                    logger.info(f"Найденная ссылка в кнопке не содержит целевой текст: {url}")
                                    return None

            return None
        except Exception as e:
            logger.error(f"Ошибка извлечения URL из сообщения: {e}")
            return None

    def extract_urls_from_text(self, text: str) -> List[str]:
        """Извлечение URLs из текста"""
        import re
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        return re.findall(url_pattern, text)

    def _check_button_text(self, button_text: str, target_text: str) -> bool:
        """Провера текста кнопки с учетом эмодзи и других символов"""
        if not button_text or not target_text:
            return False
        
        # Очищаем строки от пробелов по краям
        button_text = button_text.strip()
        target_text = target_text.strip().lower()
        
        # Проверяем вхождение целевого текста в текст нопки
        return target_text in button_text.lower()

    async def connect(self) -> Tuple[bool, Optional[str], Optional[dict], Optional[dict], Optional[dict]]:
        """Подключение к Telegram с расширенным возвратом данных"""
        try:
            logger.info("Начинаем процесс подключения к Telegram")
            await self.ensure_session_directory()
            
            # Добавляем обработку ожидаемой ошибки блокировки базы данных от телеграм
            try:
                self.client = await self.initialize_client()
                logger.debug("Клиент Telegram инициализирован")
            except Exception as e:
                if "database is locked" in str(e):
                    logger.warning("😱 !СЫНОК ТЕБЯ ВЗЛОМАЛИ! 😂 Шучу, ожидаемая ошибка, продолжаем работу: %s", str(e))
                else:
                    raise
            
            await self.client.connect()
            logger.debug("Установлено соединение с Telegram")

            # Проверка авторизации и вход
            try:
                if not await self.client.is_user_authorized():
                    logger.debug("Требуется авторизация")
                    if not await self.sign_in(self.client):
                        logger.error("Ошибка при попытке входа")
                        return False, None, None, None, None
            except AuthKeyUnregisteredError:
                logger.warning("Сессия недействительна, пересоздаем")
                if self.session_file.exists():
                    self.session_file.unlink()
                if not await self.sign_in(self.client):
                    logger.error("Ошибка при повторной попытке входа")
                    return False, None, None, None, None
            
            if not await self.client.is_user_authorized():
                logger.debug("Клиент не авторизован, начинаем процесс входа")
                if not await self.sign_in(self.client):
                    logger.error("Авторизация не удалась")
                    return False, None, None, None, None
            
            logger.info("Клиент успешно авторизован")
            
            # Поиск URL бота и получение метаданных
            url, bot_metadata = await self.find_bot_url(self.client)
            logger.debug(f"Получен URL бота: {url}")
            logger.debug(f"Получены метаданные бота: {bot_metadata}")
            
            if url:
                webapp_data = await self.prepare_webapp_data(self.client, bot_metadata)
                logger.debug(f"Подготовлены данные WebApp: {webapp_data}")
                return True, url, self.device_config, bot_metadata, webapp_data
            else:
                logger.warning("URL бота не найден")
                return True, None, self.device_config, None, None

        except Exception as e:
            logger.warning(f"Некритическая ошибка подключения: {e}")
            return False, None, None, None, None
        
    async def cleanup(self):
        """Очистка ресурсов"""
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            logger.info("Клиент отключен")

if __name__ == "__main__":
    # Для тестирования
    load_dotenv()
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")
    
    if all([api_id, api_hash, phone]):
        initialize_login(api_id, api_hash, phone)
    else:
        print("Отсутствуют необходимые переменные окружения")