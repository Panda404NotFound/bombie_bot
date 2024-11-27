# chest_action.py
import re
import sys
import asyncio
import random
import traceback
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

sys.path.append(str(Path(__file__).parent.parent.parent))

from loguru import logger
from utils import HumanBehavior
from typing import Tuple, Optional
from .cv_manager import CVManager
from .ocr_manager import OCRCoordinator
from .bombie_objects import ScreenManager
from .cordination_module import ViewportConfig, box_storage, BoxCoordinates, GameObjects

class SingletonMeta(type):
    """
    Потокобезопасная реализация метакласса Singleton.
    """
    _instances = {}
    _lock = Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
            return cls._instances[cls]

@dataclass
class ButtonActive(metaclass=SingletonMeta):
    """Состояние кнопок постоянной активации"""
    auto_skill_enabled: bool = False 
    autosell_enabled: bool = False

    def set_auto_skill(self, value: bool):
        """Установка состояния автоскилла"""
        self.auto_skill_enabled = value
        
    def set_autosell(self, value: bool):
        """Установка состояния автопродажи"""
        self.autosell_enabled = value

class ChestActions:
    def __init__(self, page):
        self.page = page
        self.objects = GameObjects()
        self.screen = ScreenManager(page, self.objects)
        self.cv_manager = CVManager()
        self.coordinator = OCRCoordinator()
        self.button_active = ButtonActive()
        # Проверяем инициализацию всех компонентов
        if not all([self.screen, self.objects, self.cv_manager, self.coordinator]):
            logger.error("Ошибка инициализации компонентов")
            raise RuntimeError("Не удалось инициализировать все необходимые компоненты")
            
        self.text_patterns = {
            'menu': {
                'ru': ['навык', 'задание', 'пригл', 'магаз'],
                'en': ['skill', 'quest', 'invite', 'shop', 'store']
            },
            'chest': {
                'ru': ['продать', 'оборудовать', 'автопродажа'],
                'en': ['sell', 'equip', 'autosell']
            }
        }
        logger.debug(f"Загружены шаблоны текста: {self.text_patterns}")

    async def get_random_safe_click(self) -> Tuple[float, float]:
        """Получение безопасных координат для клика"""
        try:
            viewport = self.objects.viewport
            safe_area = viewport.cancel_click_area
            
            # Получаем случайную точку в области
            safe_coords = self.objects.get_random_point_in_area(safe_area)
            if not safe_coords:
                logger.warning("Не удалось получить координаты в безопасной области")
                return (viewport.width / 4, viewport.height / 4)
                
            logger.debug(f"Получены координаты для safe click: {safe_coords}")
            return safe_coords
            
        except Exception as e:
            logger.error(f"Ошибка получения координат для safe click: {e}")
            return (self.objects.viewport.width / 4, self.objects.viewport.height / 4)

    # Проверка нахождения в главном меню
    async def main_menu(self) -> bool:
        """Проверка нахождения в главном меню"""
        logger.debug("Начало проверки главного меню")
        
        try:
            image = await self.screen.take_screenshot()
            zones = self.objects.zone_manager.zones
                
            # Проверяем нижнюю зону
            menu_texts = self.text_patterns['menu']['ru'] + self.text_patterns['menu']['en']
            found, confidence = self.coordinator.check_text_in_area(
                image, 
                menu_texts,
                zones['bottom'][0]
            )
            
            if found:
                logger.info(f"Найдены ключевые слова меню с уверенностью {confidence:.2f}")
                # Проверяем состояние автоскилла если находимся в меню
                if not self.button_active.auto_skill_enabled:
                    await self.auto_skill_click()
                return True
                
            logger.info("В нижней зоне не найдены требуемые ключевые слова")
            return False
            
        except Exception as e:
            logger.error(f"Ошибка проверки главного меню: {e}")
            return False

    # Проверка наличия доступных сундуков
    async def check_chest_numbers(self) -> bool:
        """Проверка наличия доступных сундуков"""
        try:
            # Получаем область с числом сундуков
            chest_area = self.objects.get_default_chest_area_numbers()
            if not chest_area:
                logger.error("Не удалось получить область сундуков")
                return False

            # Делаем скриншот области
            screenshot = await self.screen.take_screenshot(chest_area)
            if screenshot is None:
                logger.error("Не удалось получить скриншот области сундуков")
                return False

            # Распознаем текст
            number_image = self.coordinator.preprocess_image(screenshot)
            texts = self.coordinator.get_numbers_from_image(number_image)
            if not texts:
                logger.warning("Текст не распознан в области сундуков")
                return False

            # Ищем числа в тексте
            numbers = [int(s) for s in texts[0].split() if s.isdigit()]
            if not numbers:
                logger.info("Числа не найдены в тексте")
                return 1 # Возвращаем 1 если нет чисел, чтобы продолжить логику

            chest_count = numbers[0]
            logger.info(f"Найдено сундуков: {chest_count}")
            return chest_count > 0

        except Exception as e:
            logger.error(f"Ошибка при проверке количества сундуков: {e}")
            return False

    # Проверка и клик по кнопке 'Автоскилл'
    async def auto_skill_click(self):
        """Проверяем и активируем 'Автоскилл' если не включен"""
        try:
            # Получаем область автоскилла
            auto_skill_area = self.objects.get_auto_skill_button_area()
            
            # Делаем скриншот области
            screenshot = await self.screen.take_screenshot(auto_skill_area)
            if screenshot is None:
                logger.error("Не удалось получить скриншот области автоскилла")
                return False
                
            # Проверяем состояние кнопки
            is_enabled = self.cv_manager.find_auto_skill_button(screenshot)
            
            if not is_enabled:
                # Получаем координаты для клика
                auto_skill_click_area = self.objects.get_auto_skill_button_click()
                coords = self.objects.get_random_point_in_area(auto_skill_click_area)
                if not coords:
                    logger.error("Не удалось получить координаты для клика")
                    return False
                    
                # Выполняем клик
                await HumanBehavior.random_delay()
                await self.page.mouse.click(coords[0], coords[1])
                
                # Проверяем результат после клика
                await asyncio.sleep(1)
                new_screenshot = await self.screen.take_screenshot(auto_skill_area)
                is_enabled = self.cv_manager.find_auto_skill_button(new_screenshot)
                
            # Обновляем состояние в структуре
            self.button_active.set_auto_skill(is_enabled)
            logger.info(f"Состояние автоскилла установлено: {is_enabled}")
            
            return is_enabled
            
        except Exception as e:
            logger.error(f"Ошибка при работе с автоскиллом: {e}")
            return False

    # Проверка нахождения в главном меню для взаимодействия с сундуком
    async def validation_chest(self) -> bool:
        """Валидация возможности взаимодействия с сундуком"""
        attempts = 0
        while attempts < 3:
            if await self.main_menu():
                return True
                
            safe_coords = await self.get_random_safe_click()
            await HumanBehavior.random_delay()
            await self.page.mouse.click(safe_coords[0], safe_coords[1])
            await asyncio.sleep(1)
            attempts += 1
            
        return False

    # Проверка валидности открытого сундука
    async def check_valid_chest(self) -> bool:
        """Проверка валидности открытого сундука"""
        try:
            image = await self.screen.take_screenshot()
            text = await self.screen.get_text_from_area(image, self.objects.get_default_chest_area())
            return any(word in text.lower() for word in 
                      self.text_patterns['chest']['ru'] + self.text_patterns['chest']['en'])
        except Exception as e:
            logger.error(f"Ошибка проверки сундука: {e}")
            return False

    # Проверка состояния автопродажи в открытом сундуке
    async def chest_is_open_action_autosell(self) -> bool:
        """Проверка состояния автопродажи в открытом сундуке"""
        logger.debug("Начало проверки состояния автопродажи")
        
        try:
            # Проверяем состояние в структуре
            if self.button_active.autosell_enabled:
                logger.debug("Автопродажа уже активирована в структуре")
                return True
            
            # Получаем полный скриншот
            image = await self.screen.take_screenshot()
            if image is None:
                logger.error("Не удалось получить скриншот")
                return False
            
            # Получаем область чекбокса
            autosell_area = self.objects.get_default_autosell_area()
            expanded_area = self.objects.expand_area(autosell_area, 0.5)
            
            # Вырезаем область изображения для проверки
            cropped_image = image[
                int(expanded_area.top_left_y):int(expanded_area.bottom_right_y),
                int(expanded_area.top_left_x):int(expanded_area.bottom_right_x)
            ]
            
            # Проверяем состояние чекбокса через CV
            is_checked = self.cv_manager.find_autosell_checkbox(cropped_image)
            
            if is_checked:
                logger.info("Галочка автопродажи была установлена")
                self.button_active.set_autosell(True)
                return True
            
            # Если не установлена - пытаемся нажать на чекбокс
            logger.info("Галочка автопродажи не установлена, выполняем клик")
            await self.auto_sell_click()
            await HumanBehavior.random_delay()
            
            # Проверяем результат
            new_image = await self.screen.take_screenshot()
            cropped_new_image = new_image[
                int(expanded_area.top_left_y):int(expanded_area.bottom_right_y),
                int(expanded_area.top_left_x):int(expanded_area.bottom_right_x)
            ]
            is_checked = self.cv_manager.find_autosell_checkbox(cropped_new_image)
            self.button_active.set_autosell(is_checked)
            
            logger.info(f"Состояние автопродажи обновлено в структуре: {is_checked}")
            return is_checked
            
        except Exception as e:
            logger.error(f"Ошибка проверки автопродажи: {e}")
            return False

    # Клик по области автопродажи
    async def auto_sell_click(self):
        """Клик по области автопродажи"""
        try:
            autosell_area = self.objects.get_default_autosell_area()
            coords = self.objects.get_random_point_in_area(autosell_area)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(coords[0], coords[1])
        except Exception as e:
            logger.error(f"Ошибка клика автопродажи: {e}")

    # Логика принятия решения о продаже или экипировке
    async def logic_sell_or_equip(self) -> bool:
        """Логика принятия решения о продаже или экипировке"""
        try:
            # Получаем область индикатора силы
            image = await self.screen.take_screenshot()
            power_area = self.objects.get_default_power_area()
            expanded_area = self.objects.expand_area(power_area)
            
            # Вырезаем нужную область из изображения
            cropped_image = image[
                int(expanded_area.top_left_y):int(expanded_area.bottom_right_y),
                int(expanded_area.top_left_x):int(expanded_area.bottom_right_x)
            ]
            
            # Проверяем индикатор силы
            is_power_increase = self.cv_manager.find_power_checkbox(cropped_image)
            logger.info(f"Результат проверки индикатора силы: {'увеличение' if is_power_increase else 'уменьшение'}")

            if is_power_increase:
                # Логика экипировки
                logger.info("Обнаружено увеличение силы, выполняем экипировку")
                equip_coords = self.objects.get_default_equip_area()
                coords = self.objects.get_random_point_in_area(equip_coords)
                await HumanBehavior.random_delay()
                await self.page.mouse.click(coords[0], coords[1])
                logger.info("Выполнена экипировка предмета")
                await asyncio.sleep(1)
                await HumanBehavior.random_delay()
                
                # Проверяем результат экипировки
                check_image = await self.screen.take_screenshot()
                if self.cv_manager.find_incorrect_equip_choice(check_image):
                    logger.warning("Обнаружено предупреждение при экипировке, выполняем продажу")
                    # Выполняем safe click для закрытия предупреждения
                    safe_coords = await self.get_random_safe_click()
                    await HumanBehavior.random_delay()
                    await self.page.mouse.click(safe_coords[0], safe_coords[1])
                    
                    # Выполняем продажу
                    sell_coords = self.objects.get_default_sell_area()
                    coords = self.objects.get_random_point_in_area(sell_coords)
                    await HumanBehavior.random_delay()
                    await self.page.mouse.click(coords[0], coords[1])
                    logger.info("Выполнена продажа предмета после неудачной экипировки")

            else:
                # Логика продажи
                logger.info("Обнаружено уменьшение силы, выполняем продажу")
                sell_coords = self.objects.get_default_sell_area()
                coords = self.objects.get_random_point_in_area(sell_coords)
                await HumanBehavior.random_delay()
                await self.page.mouse.click(coords[0], coords[1])
                logger.info("Выполнена продажа предмета")
                await asyncio.sleep(1)
                await HumanBehavior.random_delay()
                
                # Проверяем результат продажи
                check_image = await self.screen.take_screenshot()
                if self.cv_manager.find_incorrect_equip_choice(check_image):
                    logger.warning("Обнаружено предупреждение при продаже, выполняем экипировку")
                    # Выполняем safe click для закрытия предупреждения
                    safe_coords = await self.get_random_safe_click()
                    await HumanBehavior.random_delay()
                    await self.page.mouse.click(safe_coords[0], safe_coords[1])
                    
                    # Выполняем экипировку
                    equip_coords = self.objects.get_default_equip_area()
                    coords = self.objects.get_random_point_in_area(equip_coords)
                    await HumanBehavior.random_delay()
                    await self.page.mouse.click(coords[0], coords[1])
                    logger.info("Выполнена экипировка предмета после неудачной продажи")
                
            return True
            
        except Exception as e:
            logger.error(f"Ошибка в логике продажи/экипировки: {e}")
            return False

    # Управление процессом продажи или экипировки
    async def chest_sell_or_equip(self) -> bool:
        """Управление процессом продажи или экипировки"""
        if not await self.check_valid_chest():
            if not await self.main_menu():
                return False
            # Повторяем попытку входа в сундук
            chest_area = self.objects.get_default_chest_area()
            coords = self.objects.get_random_point_in_area(chest_area)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(coords[0], coords[1])
            
        # Проверяем состояние автопродажи из структуры
        if not self.button_active.autosell_enabled:
            if not await self.chest_is_open_action_autosell():
                return False
        
        return await self.logic_sell_or_equip()

    # Основная функция обработки сундука
    async def process_chest(self, attempt: int = 0) -> str:
        """Основная функция обработки сундука
        Returns:
            'continue' - если сундук обработан успешно и нужно продолжить
            'done' - если сундуков нет
            'error' - если произошла ошибка
        """
        logger.info(f"Начало обработки сундука (попытка {attempt}/3)")
        
        if attempt >= 3:
            logger.warning("Превышено максимальное количество попыток, нажимаем кнопку назад")
            # Нажимаем кнопку назад
            back_button = self.objects.get_default_back_button()
            back_coords = self.objects.get_random_point_in_area(back_button)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(back_coords[0], back_coords[1])
            await asyncio.sleep(1)
            return 'error'
        
        try:
            # Проверка главного меню
            logger.debug("Проверка нахождения в главном меню")
            if not await self.main_menu():
                logger.warning("Не в главном меню, выполняем safe click")
                # Получаем область безопасного клика
                safe_area = self.objects.viewport.cancel_click_area
                if not safe_area:
                    logger.error("Не удалось получить области безопасного клика")
                    return 'error'
                    
                # Выбираем случайную область для нажатия на безопасную область для выхода в главное меню
                safe_coords = self.objects.get_random_point_in_area(safe_area)
                if not safe_coords:
                    logger.error("Не удалось получить координаты для клика")
                    return 'error'
                    
                logger.debug(f"Выбраны координаты для safe click: {safe_coords}")
                
                await HumanBehavior.random_delay()
                await self.page.mouse.click(safe_coords[0], safe_coords[1])
                return await self.process_chest(attempt + 1)
                
            # Проверка наличия сундуков
            if not await self.check_chest_numbers():
                logger.info("Доступных сундуков нет, переходим в режим ожидания")
                return 'done'

            # Пытаемся залутать плюшки в процессе открытия сундука
            await self.page.mouse.click(73, 703)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(73, 703)
            await HumanBehavior.random_delay()

            # Клик по сундуку
            logger.debug("Получение области сундука")
            chest_area = self.objects.get_default_chest_area()
            if not isinstance(chest_area, BoxCoordinates):
                logger.error(f"Некорректный тип chest_area: {type(chest_area)}")
                return 'error'
                
            chest_coords = self.objects.get_random_point_in_area(chest_area)
            logger.info(f"Выбраны координаты для клика по сундуку: {chest_coords}")
            
            await HumanBehavior.random_delay()
            # before_image = await self.screen.take_screenshot()
            await self.page.mouse.click(chest_coords[0], chest_coords[1])
            await HumanBehavior.random_delay()
            await asyncio.sleep(1)

            # Проверка автопродажи
            if not await self.chest_is_open_action_autosell():
                logger.warning("Не удалось настроить автопродажу")
                return await self.process_chest(attempt + 1)
                
            # Обработка предметов
            if not await self.logic_sell_or_equip():
                logger.warning("Не удалось обработать предметы")
                return await self.process_chest(attempt + 1)
                
            logger.info("Успешная обработка сундука, продолжаем обработку")
            return 'continue'
            
        except Exception as e:
            logger.error(f"Критическая ошибка обаботки сундка: {e}")
            return 'error'