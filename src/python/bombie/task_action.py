# tast_action.py
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
from .chest_action import ChestActions
from .cordination_module import ViewportConfig, box_storage, BoxCoordinates, GameObjects

class TaskActions:
    def __init__(self, page):
        self.page = page
        self.objects = GameObjects()
        self.chest_actions = ChestActions(page)
        self.screen = ScreenManager(page, self.objects)
        self.cv_manager = CVManager()
        self.coordinator = OCRCoordinator()
        # Проверяем инициализацию всех компонентов
        if not all([self.screen, self.objects, self.cv_manager, self.coordinator]):
            logger.error("Ошибка инициализации компонентов")
            raise RuntimeError("Не удалось инициализировать все необходимые компоненты")
            
        self.text_patterns = {
            'rewards': {
                'ru': ['начать', 'получить', 'получен'],
                'en': ['start', 'get', 'received']
            }
        }
        logger.debug(f"Загружены шаблоны текста: {self.text_patterns}")\


# РАЗДЕЛЕНИЕ БЛОКА ОБЩИЙ ФУНКЦИЙ
# МЕЖДУ БЛОКАМИ ФУНКЦИЙ ЛОГИКИ
# ДЛЯ ОТКРЫТИЯ ЗАДАНИЙ И СБОРА НАГРАД

    # Функция выполнения нажатия на "Задания"
    async def click_task_button(self) -> bool:
        """Нажатие на кнопку 'Задание'"""
        task_button_area = self.objects.get_default_task_button()
        if not isinstance(task_button_area, BoxCoordinates):
            logger.error(f"Некорректный тип task_button_area: {type(task_button_area)}")
            return False 

        # Выбираем случайную область для нажатия на кнопку 'Задание'
        task_coords = self.objects.get_random_point_in_area(task_button_area)
        if not task_coords:
            logger.error("Не удалось получить координаты для клика")
            return False
            
        logger.debug(f"Выбраны координаты для клика по заданию: {task_coords}")
        
        await HumanBehavior.random_delay()
        await self.page.mouse.click(task_coords[0], task_coords[1])
        await HumanBehavior.random_delay()
        return True

    # Функция выхода в безопасную зону если мы не в главном меню
    async def back_to_main_menu(self) -> bool:
        """Выход в безопасную зону"""
        # Получаем область безопасного клика
        safe_area = self.objects.viewport.cancel_click_area
        if not safe_area:
            logger.error("Не удалось получить области безопасного клика")
            return False
            
        # Выбираем случайную область для нажатия на безопасную область для выхода в главное меню 
        safe_coords = self.objects.get_random_point_in_area(safe_area)
        if not safe_coords:
            logger.error("Не удалось получить координаты для клика")
            return False
            
        logger.debug(f"Выбраны координаты для safe click: {safe_coords}")
        
        await HumanBehavior.random_delay()
        await self.page.mouse.click(safe_coords[0], safe_coords[1])

    # Функция проверки окна для продолжения после действий 
    async def click_to_continue(self) -> bool:
        """Обработка кликов для продолжения"""
        try:
            logger.info("Проверка необходимости клика для продолжения")
            image = await self.screen.take_screenshot()
            if image is None:
                logger.error("Не удалось получить скриншот")
                return False
            
            # Проверяем наличие текста
            continue_texts = [
                'нажмите', 'область', 'закрыть',
                'click', 'area', 'close'
            ]
            
            result, confidence = self.coordinator.check_text_in_area(
                image,
                continue_texts,
                threshold=0.2
            )
            
            if result and confidence > 0.6:
                logger.info(f"Обнаружен текст для продолжения (confidence: {confidence:.2f})")
                # Получаем координаты для безопасного клика
                safe_coords = self.objects.get_random_point_in_area(
                    self.objects.viewport.cancel_click_area
                )
                if not safe_coords:
                    logger.error("Не удалось получить координаты для клика")
                    return False
                
                logger.debug(f"Выполняем клик для продолжения: {safe_coords}")
                await HumanBehavior.random_delay()
                await self.page.mouse.click(safe_coords[0], safe_coords[1])
                await asyncio.sleep(0.7)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при обработке клика для продолжения: {e}")
            return False

# РАЗДЕЛЕНИЕ БЛОКА ОБЩИЙ ФУНКЦИЙ
# МЕЖДУ БЛОКАМИ ФУНКЦИЙ ЛОГИКИ
# ДЛЯ ОТКРЫТИЯ ЗАДАНИЙ И СБОРА НАГРАД

    # Функция проверки наличия доступных ежедневных наград на кнопке заданий
    async def check_daily_rewards(self) -> bool:
        """Проверка наличия доступных ежедневных наград на кнопке заданий"""
        try:
            '''
            logger.info("Проверка наличия доступных ежедневных наград")
            # Получаем область кнопки заданий с расширением
            task_button_area = self.objects.get_default_task_button()
            expanded_area = self.objects.expand_area(task_button_area, 0.4)
            
            # Делаем скриншот расширенной области
            screenshot = await self.screen.take_screenshot(expanded_area)
            if screenshot is None:
                logger.error("Не удалось получить скриншот")
                return False
                
            # Проверяем состояние наград
            result = self.cv_manager.find_daily_task_rewards(screenshot)
            logger.debug(f"Результат проверки ежедневных наград: {result}")

            return result
            '''
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при проверке ежедневных наград: {e}")
            return False

    # Функция проверки нахождения в меню заданий
    async def check_task_menu(self, retry_count=0) -> bool:
        """
        Проверка нахождения в меню заданий
        Нужно изменить логику проверки самой кнопки и ее совпадений
        Через CV manager.
        """
        try:
            image = await self.screen.take_screenshot()
            if image is None:
                logger.error("Не удалось получить скриншот")
                return False
                
            # Проверяем наличие текста "Daily Task" в области
            task_area = self.objects.get_default_dayli_task_button()
            result, confidence = self.coordinator.check_text_in_area(
                image,
                ['Dayli task', 'Task', 'Dally' 'task', 'начать', 'получен', 'start', 'get', 'Permanent Task'],
                task_area,
                threshold=0.45
            )
            
            logger.debug(f"Проверка меню заданий: {result} (confidence: {confidence:.2f})")
            
            # Если первая попытка не удалась, пробуем еще раз
            if not result and retry_count == 0:
                logger.info("Первая попытка проверки меню не удалась, пробуем еще раз")
                await asyncio.sleep(1.0)  # Добавляем задержку перед повторной попыткой
                return await self.check_task_menu(retry_count=1)
            # Если вторая попытка не удалась, перезапускаем process_daily_tasks
            elif not result and retry_count == 1:
                logger.warning("Вторая попытка проверки меню не удалась, перезапускаем process_daily_tasks")
                await self.process_daily_tasks()
                
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при проверке меню заданий: {e}")
            return False
            
    # Функция открытия меню ежедневных заданий
    async def open_daily_tasks(self) -> bool:
        """Открытие меню ежедневных заданий"""
        try:
            logger.info("Начало открытия меню ежедневных заданий")
            # Клик по кнопке заданий
            await asyncio.sleep(10.0)
            if not await self.click_task_button():
                return False
            
            # Получаем координаты кнопки Daily Task
            await asyncio.sleep(0.7)
            logger.info("Получение координат кнопки Daily Task")
            daily_task_area = self.objects.get_default_dayli_task_button()
            coords = self.objects.get_random_point_in_area(daily_task_area)
            
            # Выполняем клик
            logger.info(f"Выполнение клика по кнопке Daily Task: {coords}")
            await HumanBehavior.random_delay()
            await self.page.mouse.click(coords[0], coords[1])
            
            # Ждем загрузки вкладки заданий
            logger.info("Ожидание загрузки вкладки заданий")
            await asyncio.sleep(1.5)
            
            # Проверяем, что вкладка заданий открылась
            logger.info("Проверка, что вкладка заданий открылась")
            return await self.check_task_menu()
            
        except Exception as e:
            logger.error(f"Ошибка при открытии ежедневных заданий: {e}")
            return False
            
    async def check_rewards_available(self) -> bool:
        """Проверка наличия доступных наград"""
        try:
            logger.info("Начало проверки наличия доступных наград")
            '''
            # Получаем область наград и расширяем её на 40%
            rewards_area = self.objects.get_default_daily_task_rewards_button()
            expanded_area = self.objects.expand_area(rewards_area, 0.4)
            screenshot = await self.screen.take_screenshot(expanded_area)
            '''
            screenshot = await self.screen.take_screenshot()
            if screenshot is None:
                logger.error("Не удалось получить скриншот области наград")
                return False
                
            # Проверяем наличие текста "Получить"
            result, confidence = self.coordinator.check_text_in_area(
                screenshot,
                ['получ', 'получить', 'get'],
                threshold=0.6
            )
            logger.debug(f"Проверка наличия доступных наград: {result} (confidence: {confidence:.2f})")

            if result:
                logger.info("Обнаружены доступные награды")
                return True
            
            if not result:
                # Проверяем необходимость клика для продолжения
                if await self.click_to_continue():
                    logger.info("Выполнен клик для продолжения, повторяем проверку наград")
                    return await self.check_rewards_available()
                return False
            
        except Exception as e:
            logger.error(f"Ошибка при проверке наград: {e}")
            return False
            
    # Функция сбора наград за ежедневные задания
    async def collect_rewards(self) -> bool:
        """Сбор наград за ежедневные задания"""
        try:
            logger.info("Начало сбора наград")
            while True:
                # Проверяем наличие наград
                if not await self.check_rewards_available():
                    logger.info("Нет доступных наград")
                    return 'done'  # Возвращаем True, так как все награды собраны

                # Нажимаем повторно на вкладку   
                logger.info("Нажимаем повторно на кнопку Daily Task")
                daily_task_area = self.objects.get_default_dayli_task_button()
                coords_task = self.objects.get_random_point_in_area(daily_task_area)
                await HumanBehavior.random_delay()
                await self.page.mouse.click(coords_task[0], coords_task[1])
                await asyncio.sleep(0.5)

                # Получаем координаты кнопки наград
                rewards_area = self.objects.get_default_daily_task_rewards_button()
                coords = self.objects.get_random_point_in_area(rewards_area)
                
                # Выполняем клик
                await HumanBehavior.random_delay()
                await self.page.mouse.click(coords[0], coords[1])
                
                # Ждем анимацию получения наград
                await asyncio.sleep(0.7)
                await self.collect_rewards()
                
        except Exception as e:
            logger.error(f"Ошибка при сборе наград: {e}")
            return False
            


# НИЖЕ БЛОК ОСНОВНЫХ ФУНКЦИЙ
# КОТОРЫЕ СОБИРАЮТ ХАЛЯВУ
# НЕ ГИБКИЙ ПРЯМОЙ ПОДХОД


    # Основная функция обработки ежедневных заданий
    async def process_daily_tasks(self) -> str:
        """Основная функция обработки ежедневных заданий
        
        Returns:
            'continue' - если награды собраны успешно
            'done' - если нет доступных наград
            'error' - если произошла ошибка
        """
        try:
            logger.info("Начало обработки ежедневных заданий")

            # Обрабатываем бесплатные награды
            free_rewards_result = await self.process_free_dayli_rewards()
            if not free_rewards_result:
                logger.error("Ошибка при обработке бесплатных наград")
                return 'done'

            # Проверка главного меню
            if not await self.chest_actions.main_menu():
                logger.warning("Не в главном меню")
                await self.back_to_main_menu()
                await asyncio.sleep(0.5)
                return await self.process_daily_tasks()

            # Проверяем наличие доступных наград
            if not await self.check_daily_rewards():
                logger.info("Нет доступных наград")
                await self.back_to_main_menu()
                await HumanBehavior.random_delay()
                return 'done'
            
            # Открываем меню заданий
            if not await self.open_daily_tasks():
                logger.error("Не удалось открыть меню заданий")
                return 'done'
            
            # Проверяем наличие наград
            await asyncio.sleep(1.4)
            if not await self.check_rewards_available():
                logger.info("Нет доступных наград")
                await self.back_to_main_menu()
                await HumanBehavior.random_delay()
                return 'done'
            
            # Собираем награды
            if not await self.collect_rewards():
                logger.error("Не удалось собрать награды")
                await self.back_to_main_menu()
                await HumanBehavior.random_delay()
                return 'done'
            
            logger.info("Обработка всех наград завершена")

            return 'continue'
            
        except Exception as e:
            logger.error(f"Ошибка при обработке ежедневных заданий: {e}")
            return 'error'

    # Глобальная функция сбора разных бесплатных плюшек 
    async def process_free_dayli_rewards(self) -> bool:
        """Глобальная функция сбора разных бесплатных плюшек
        
        Returns:
            bool: True если все награды собраны успешно, False в случае ошибки
        """
        try:
            logger.info("Начало процесса сбора бесплатных наград")

            # Проверяем, что мы в главном меню перед началом
            if not await self.chest_actions.main_menu():
                logger.warning("Не в главном меню, возвращаемся")
                await self.back_to_main_menu()
                await asyncio.sleep(1)
                await HumanBehavior.random_delay()
                if not await self.chest_actions.main_menu():
                    logger.error("Не удалось вернуться в главное меню перед началом сбора наград")
                    return False

            # Нажимаем на кнопку "Пригласить"
            invite_invite_main = self.objects.get_default_invite_main_button()
            invite_main_coords = self.objects.get_random_point_in_area(invite_invite_main)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(invite_main_coords[0], invite_main_coords[1])
            await asyncio.sleep(5)

            # Нажимаем на кнопку "Пригласить друга"
            invite_friend = self.objects.get_default_invite_friend_button()
            invite_friend_coords = self.objects.get_random_point_in_area(invite_friend)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(invite_friend_coords[0], invite_friend_coords[1])
            await asyncio.sleep(5)

            # Повторный клик
            await HumanBehavior.random_delay()
            await self.page.mouse.click(invite_friend_coords[0], invite_friend_coords[1])
            await asyncio.sleep(1)

            # Нажимаем на кнопку "Daily Rewards"
            dayli_reward =  self.objects.get_default_invite_dayli_reward_button()
            dayli_reward_coords = self.objects.get_random_point_in_area(dayli_reward)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(dayli_reward_coords[0], dayli_reward_coords[1])
            await asyncio.sleep(5)

            # Нажимаем на кнопку "Получить"
            get_reward_get =  self.objects.get_default_invite_dayli_reward_get_button()
            get_reward_coords = self.objects.get_random_point_in_area(get_reward_get)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(get_reward_coords[0], get_reward_coords[1])
            await asyncio.sleep(3)

            # Повторный клик
            await HumanBehavior.random_delay()
            await self.page.mouse.click(get_reward_coords[0], get_reward_coords[1])
            await asyncio.sleep(1)

            # Нажимаем на область отмены
            cancel_area = self.objects.viewport.cancel_click_area
            cancel_coords = self.objects.get_random_point_in_area(cancel_area)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(cancel_coords[0], cancel_coords[1])
            await asyncio.sleep(1)

            # Нажимаем на кнопку "Назад"
            back_button = self.objects.get_default_back_button()
            back_button_coords = self.objects.get_random_point_in_area(back_button)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(back_button_coords[0], back_button_coords[1])
            await asyncio.sleep(0.5)

            # Проверяем, что мы в главном меню после приглашений
            if not await self.chest_actions.main_menu():
                logger.warning("Не в главном меню, возвращаемся")
                await self.back_to_main_menu()
                await asyncio.sleep(1)
                await HumanBehavior.random_delay()
                if not await self.chest_actions.main_menu():
                    logger.error("Не удалось вернуться в главное меню перед началом сбора наград")
                    return False

            # Нажимаем на кнопку "Магазин"
            magazine_coord = self.objects.get_default_magazine_button()
            magazine_coords = self.objects.get_random_point_in_area(magazine_coord)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(magazine_coords[0], magazine_coords[1])
            await asyncio.sleep(5)

            # Нажимаем на кнопку "Получить сундук"
            free_chest = self.objects.get_default_magazine_free_chest()
            free_chest_coords = self.objects.get_random_point_in_area(free_chest)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(free_chest_coords[0], free_chest_coords[1])
            await asyncio.sleep(2)

            # Повторный клик
            await HumanBehavior.random_delay()
            await self.page.mouse.click(free_chest_coords[0], free_chest_coords[1])
            await asyncio.sleep(1)

            # Нажимаем на область отмены
            await HumanBehavior.random_delay()
            await self.page.mouse.click(cancel_coords[0], cancel_coords[1])

            # Проверка главного меню
            if not await self.chest_actions.main_menu():
                logger.warning("Не в главном меню, возвращаемся")
                await self.back_to_main_menu()
                await asyncio.sleep(1)
                await HumanBehavior.random_delay()
                if not await self.chest_actions.main_menu():
                    logger.error("Не удалось вернуться в главное меню перед началом сбора наград")
                    return False

            # Нажимаем на кнопку "Кубок"
            kubok_area = self.objects.get_default_kubok_free_rewards_area()
            kubok_coords = self.objects.get_random_point_in_area(kubok_area)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(kubok_coords[0], kubok_coords[1])
            await asyncio.sleep(5)

            # Нажимаем на кнопку "Лайк"
            like_area = self.objects.get_default_kubok_free_rewards_like()
            like_coords = self.objects.get_random_point_in_area(like_area)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(like_coords[0], like_coords[1])
            await asyncio.sleep(1)

            # Повторный клик на "Лайк"
            await HumanBehavior.random_delay()
            await self.page.mouse.click(like_coords[0], like_coords[1])
            await asyncio.sleep(1)

            # Нажимаем на кнопку "Назад"
            back_button = self.objects.get_default_back_button()
            back_coords = self.objects.get_random_point_in_area(back_button)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(back_coords[0], back_coords[1])
            await asyncio.sleep(0.5)

            # Еще одна проверка главного меню
            if not await self.chest_actions.main_menu():
                logger.warning("Не в главном меню, возвращаемся")
                await self.back_to_main_menu()
                await asyncio.sleep(1)
                await HumanBehavior.random_delay()
                if not await self.chest_actions.main_menu():
                    logger.error("Не удалось вернуться в главное меню")
                    return False

            # Клик на фиксированные координаты
            await HumanBehavior.random_delay()
            await self.page.mouse.click(92, 66)
            await asyncio.sleep(5)

            # Клик на кнопку сбора вознаграждений в конверте
            message_rewards = self.objects.get_default_message_free_rewards()
            message_coords = self.objects.get_random_point_in_area(message_rewards)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(message_coords[0], message_coords[1])
            await asyncio.sleep(1)

            # Повторный клик на ту же область
            await HumanBehavior.random_delay()
            await self.page.mouse.click(message_coords[0], message_coords[1])
            await asyncio.sleep(1)

            # Клик на область отмены
            cancel_area = self.objects.viewport.cancel_click_area
            cancel_coords = self.objects.get_random_point_in_area(cancel_area)
            await HumanBehavior.random_delay()
            await self.page.mouse.click(cancel_coords[0], cancel_coords[1])
            await asyncio.sleep(1)

            # Еще одна проверка главного меню
            if not await self.chest_actions.main_menu():
                logger.warning("Не в главном меню, возвращаемся")
                await self.back_to_main_menu()
                await asyncio.sleep(1)
                await HumanBehavior.random_delay()
                if not await self.chest_actions.main_menu():
                    logger.error("Не удалось вернуться в главное меню")
                    return False

            logger.info("Процесс сбора бесплатных наград завершен успешно")
            return True

        except Exception as e:
            logger.error(f"Ошибка в процессе сбора бесплатных наград: {e}")
            return False