from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional
from loguru import logger
import asyncio
from datetime import datetime, timedelta

class ModuleState(Enum):
    """Состояния модуля"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"

@dataclass
class ModuleInfo:
    """Информация о модуле"""
    name: str
    state: ModuleState = ModuleState.STOPPED
    task: Optional[asyncio.Task] = None
    start_time: Optional[datetime] = None
    stop_time: Optional[datetime] = None
    error_message: Optional[str] = None
    next_run_time: Optional[datetime] = None
    wait_duration: Optional[float] = None

class ModuleRegistry:
    """Реестр модулей"""
    _instance = None
    
    # Функция создания экземпляра класса
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModuleRegistry, cls).__new__(cls)
            cls._instance.modules: Dict[str, ModuleInfo] = {}
        return cls._instance

    # Функция регистрации нового модуля
    def register_module(self, name: str) -> ModuleInfo:
        """Регистрация нового модуля"""
        if name not in self.modules:
            self.modules[name] = ModuleInfo(name=name)
            logger.info(f"Зарегистрирован новый модуль: {name}")
        return self.modules[name]

    # Функция получения информации о модуле
    def get_module(self, name: str) -> Optional[ModuleInfo]:
        """Получение информации о модуле"""
        return self.modules.get(name)

    # Функция обновления состояния модуля
    def update_state(self, name: str, state: ModuleState, error: str = None, wait_duration: float = None):
        """Обновление состояния модуля"""
        if module := self.modules.get(name):
            module.state = state
            if state == ModuleState.RUNNING:
                module.start_time = datetime.now()
                module.next_run_time = None
            elif state == ModuleState.PAUSED:
                module.stop_time = datetime.now()
                if wait_duration is not None:
                    module.wait_duration = wait_duration
                    module.next_run_time = datetime.now() + timedelta(seconds=wait_duration)
                else:
                    module.wait_duration = None
                    module.next_run_time = None
            elif state in [ModuleState.STOPPED, ModuleState.ERROR]:
                module.stop_time = datetime.now()
                module.next_run_time = None
            if error:
                module.error_message = error
            logger.info(f"Модуль {name} перешел в состояние {state.value}")
            if wait_duration is not None:
                logger.info(f"Установлено время ожидания: {wait_duration} сек")

class ModuleController:
    """Контроллер модулей"""
    def __init__(self):
        self.registry = ModuleRegistry()

    # Функция запуска модуля
    async def start_module(self, name: str, coroutine) -> bool:
        """Запуск модуля"""
        try:
            module = self.registry.get_module(name)
            if not module:
                module = self.registry.register_module(name)
            
            if module.state == ModuleState.RUNNING:
                logger.warning(f"Модуль {name} уже запущен")
                return False

            module.task = asyncio.create_task(coroutine)
            self.registry.update_state(name, ModuleState.RUNNING)
            logger.info(f"Модуль {name} успешно запущен")
            return True

        except Exception as e:
            logger.error(f"Ошибка запуска модуля {name}: {e}")
            self.registry.update_state(name, ModuleState.ERROR, str(e))
            return False

    # Функция остановки модуля
    async def stop_module(self, name: str) -> bool:
        """Остановка модуля"""
        try:
            module = self.registry.get_module(name)
            if not module or module.state != ModuleState.RUNNING:
                logger.warning(f"Модуль {name} не запущен")
                return False

            if module.task:
                module.task.cancel()
                try:
                    await module.task
                except asyncio.CancelledError:
                    pass
                
            self.registry.update_state(name, ModuleState.STOPPED)
            logger.info(f"Модуль {name} успешно остановлен")
            return True

        except Exception as e:
            logger.error(f"Ошибка остановки модуля {name}: {e}")
            self.registry.update_state(name, ModuleState.ERROR, str(e))
            return False

    # Функция получения списка активных модулей
    def get_active_modules(self) -> Dict[str, ModuleState]:
        """Получение списка активных модулей"""
        return {
            name: module.state 
            for name, module in self.registry.modules.items() 
            if module.state == ModuleState.RUNNING
        }

    # Функция получения статуса модуля
    def get_module_status(self, name: str) -> Optional[ModuleState]:
        """Получение статуса модуля"""
        if module := self.registry.get_module(name):
            return module.state
        return None