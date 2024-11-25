# bot_logic.py
import asyncio
import random
from typing import Optional, Dict
from loguru import logger
from playwright.async_api import Page
from utils import HumanBehavior
from .chest_action import ChestActions
from .task_action import TaskActions
from .module_manager import ModuleController, ModuleState
from datetime import datetime, timedelta

class WebAppLogic:
    def __init__(self, page: Page):
        self.page = page
        self.human = HumanBehavior()
        self.is_running = True
        self.module_controller = ModuleController()

    # ВАЖНАЯ ЛОГИКА! 
    # МОДУЛЬЯ КОНТРОЛЯ!
    # УПРАВЛЯЕТ ЛОГИЧЕСКИМИ МОДУЛЯМИ!

    # Запуск модуля через контроллер
    async def start_module(self, module_name: str, coroutine) -> bool:
        """Запуск модуля через контроллер"""
        return await self.module_controller.start_module(module_name, coroutine)

    # Остановка модуля через контроллер
    async def stop_module(self, module_name: str) -> bool:
        """Остановка модуля через контроллер"""
        return await self.module_controller.stop_module(module_name)

    # Получение списка активных модулей
    def get_active_modules(self) -> Dict[str, ModuleState]:
        """Получение списка активных модулей"""
        return self.module_controller.get_active_modules()

    # Инициализация и установка порядка запуска модулей
    def correct_starting_modules(self):
        """Инициализация и установка порядка запуска модулей"""
        # Регистрируем модули
        self.module_controller.registry.register_module("daily_tasks_processor")
        self.module_controller.registry.register_module("chest_processor")

        # Устанавливаем начальные состояния и время запуска
        current_time = datetime.now()

        # Модуль ежедневных заданий запускаем сразу
        self.module_controller.registry.update_state(
            "daily_tasks_processor",
            ModuleState.PAUSED,
            wait_duration=0  # Запуск сразу
        )
        
        # Модуль сундуков будет запущен после завершения ежедневных заданий
        self.module_controller.registry.update_state(
            "chest_processor",
            ModuleState.PAUSED,
            wait_duration=None  # Будет запланирован позже
        )


    # ВАЖНАЯ ЛОГИКА! 
    # МОДУЛЬЯ КОНТРОЛЯ!
    # УПРАВЛЯЕТ ЛОГИЧЕСКИМИ МОДУЛЯМИ!

    async def start_click(self):
        """Эмуляция нажатия на кнопку приложения"""
        try:
            # Генерируем случайные координаты в заданном диапазоне
            x = random.uniform(243, 280)
            y = random.uniform(742, 751)
            
            logger.info(f"Выполняем клик по координатам x:{x:.2f}, y:{y:.2f}")
            
            # Добавляем задержку перед кликом для эмуляции человеческого поведения
            delay = await self.human.random_delay()
            logger.debug(f"Задержка перед кликом: {delay:.3f} сек")
            await asyncio.sleep(delay)
            
            # Выполняем клик
            await self.page.mouse.click(x, y)
            logger.info("Клик успешно выполнен")
            
            # Добавляем небольшую задержку после клика
            await asyncio.sleep(0.5)
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении клика: {e}")
            return False

    # Основная функция и логика взаимодействия с Bombie ботом
    async def start_logic(self):
        """Основная логика взаимодействия с WebApp"""
        try:
            logger.info("Запуск основной логики WebApp")
            
            logger.info("Выполняем клик")
            
            # Выполняем клик
            if not await self.start_click():
                logger.error("Ошибка клика, пропускаем")
                return False

            delay = random.uniform(0.100, 0.700)
            logger.debug(f"Пауза после клика: {delay:.3f} сек")
            await asyncio.sleep(delay)

            # Запускаем цикл обработки сундуков
            # Здесь начинается запуск всех основных логических блоков и модулей

            # Здесь можно добавить дополнительную 
            # логику контроля запуска и контроля модулей
            
            # Ожидаем загрузку игрового процесса
            await asyncio.sleep(10.5)

            # Запускаем контроль процессов вместо прямого запуска модулей
            if not await self.control_processes():
                logger.error("Ошибка в контроле процессов")
                return False

            # Здесь заканчивается запуск основных
            # и логических модулей проекта 

            return True
                
        except Exception as e:
            logger.error(f"Ошибка в логике WebApp: {e}")
            return False

    # ЗДЕСЬ НАХОДЯТСЯ
    # ОСНОВНЫЕ МОДУЛИ
    # И ЛОГИЧЕСКИЕ БЛОКИ

    # Основной цикл обработки сундуков
    async def process_chests_loop(self) -> bool:
        """
        Цикл обработки сундуков
        
        Returns:
            bool: True если обработка успешна, False в случае ошибки
        """
        try:
            logger.info("Запуск цикла обработки сундуков")
            
            while self.is_running:
                # Проверка состояния модуля
                module_state = self.module_controller.get_module_status("chest_processor")
                if module_state != ModuleState.RUNNING:
                    logger.info(f"Модуль chest_processor в состоянии {module_state}, завершаем цикл")
                    break

                chest_actions = ChestActions(self.page)
                result = await chest_actions.process_chest()
                
                if result == 'done':
                    # Устанавливаем время ожидания и переводим в PAUSED
                    wait_time = 600 + 5  # 600 секунд + 5 секунд
                    self.module_controller.registry.update_state(
                        "chest_processor", 
                        ModuleState.PAUSED, 
                        wait_duration=wait_time
                    )
                    logger.info(f"Переход в режим ожидания на {wait_time} секунд")
                    break
                    
                elif result == 'continue':
                    # Успешно обработали сундук, продолжаем
                    logger.info("Сундук обработан успешно, продолжаем")
                    continue
                    
                else:  # result == 'error'
                    # Произошла ошибка, делаем паузу
                    logger.warning("Ошибка обработки сундука, ожидание 5 секунд")
                    await asyncio.sleep(5)
                    continue
                
        except Exception as e:
            logger.error(f"Критическая ошибка в цикле обработки сундуков: {e}")
            return False

    # Основной цикл обработки ежедневных заданий
    async def process_daily_tasks_loop(self) -> bool:
        """
        Цикл обработки ежедневных заданий
        
        Returns:
            bool: True если обработка успешна, False в случае ошибки
        """
        try:
            logger.info("Запуск цикла обработки ежедневных заданий")
            
            while self.is_running:
                # Проверка состояния модуля
                module_state = self.module_controller.get_module_status("daily_tasks_processor")
                if module_state != ModuleState.RUNNING:
                    logger.info(f"Модуль daily_tasks_processor в состоянии {module_state}, завершаем цикл")
                    break

                # Обрабатываем ежедневные задания
                task_actions = TaskActions(self.page)
                result = await task_actions.process_daily_tasks()
                
                match result:
                    case 'continue':
                        logger.info("Награды успешно собраны, продолжаем")
                        await asyncio.sleep(1)
                        continue
                    case 'done':
                        # Устанавливаем время ожидания и переводим в PAUSED
                        wait_time = 1800 + 5  # 1800 секунд + 5 секунд
                        self.module_controller.registry.update_state(
                            "daily_tasks_processor", 
                            ModuleState.PAUSED, 
                            wait_duration=wait_time
                        )
                        logger.info(f"Переход в режим ожидания на {wait_time} секунд")
                        # Планируем запуск модуля сундуков
                        self.module_controller.registry.update_state(
                            "chest_processor",
                            ModuleState.PAUSED,
                            wait_duration=0  # Запуск сразу после ежедневных заданий
                        )
                        logger.info(f"Переход в режим ожидания на {wait_time} секунд")
                        break
                    case 'error':
                        logger.error("Ошибка при обработке ежедневных заданий")
                        continue
                    case _:
                        logger.error(f"Неизвестный результат: {result}")
                        continue
                    
        except Exception as e:
            logger.error(f"Критическая ошибка в цикле ежедневных заданий: {e}")
            return False

    # ЗДЕСЬ НАХОДЯТСЯ
    # ОСНОВНЫЕ МОДУЛИ
    # И ЛОГИЧЕСКИЕ БЛОКИ

############################################
# !  БАБКИ МУТЯТСЯ, ЛАВЕШКА КРУТИТСЯ     ! #
# !  НЕ ЗАБУДЬ ПОЦЕЛОВАТЬ МАМУ СЕГОДНЯ   ! # 
# !  ЗА ТО ЧТО РОДИЛА ТАКОЕ ЧУДО КАК ТЫ  ! #
############################################

    # ЗДЕСЬ НАХОДЯТСЯ
    # ФУНКЦИИ КОНТРОЛЯ 
    # ВЫПОЛНЕНИЯ ПРОЦЕССОВ


    # Основная функция контроля процессов бота
    async def control_processes(self):
        """Контроль процессов бота"""
        logger.info("Запуск контроля процессов бота")
        try:

            # Инициализируем модули и их порядок запуска
            self.correct_starting_modules()
            
            while self.is_running:
                active_modules = self.get_active_modules()
                logger.info(f"Активные модули: {active_modules}")
                current_time = datetime.now()

                # Если нет активных модулей
                if not active_modules:
                    # Проверяем модули в заданном порядке
                    for module_name in ["daily_tasks_processor", "chest_processor"]:
                        module = self.module_controller.registry.get_module(module_name)
                        if module.state == ModuleState.PAUSED and module.next_run_time is not None:
                            if module.next_run_time <= current_time:
                                logger.info(f"Запуск модуля {module_name}")
                                if module_name == "daily_tasks_processor":
                                    await self.start_module(module_name, self.process_daily_tasks_loop())
                                elif module_name == "chest_processor":
                                    await self.start_module(module_name, self.process_chests_loop())
                                break  # Запускаем по одному модулю за раз
                else:
                    # Ожидаем завершения активного модуля
                    pass

                await asyncio.sleep(1)  # Короткая пауза для проверки состояний
        except Exception as e:
            logger.error(f"Ошибка в контроле процессов: {e}")
            return False