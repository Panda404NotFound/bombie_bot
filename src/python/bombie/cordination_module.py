# cordination_module.py
import json
import glob
import os
import random
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Set, List, Tuple, Optional
from loguru import logger
from PIL import Image
from .data_class import BoxCoordinates, BoxObject, GlobalBoxStorage, box_storage
from .ocr_manager import OCRManager

@dataclass
class ViewportConfig:
    """Конфигурация viewport с динамическими размерами"""
    height: int = 815  # значение по умолчанию
    width: int = 412   # значение по умолчанию

    @property
    def cancel_click_area(self) -> BoxCoordinates:
        """Область для клика отмены/закрытия"""
        width = self.width
        height = self.height
        
        return BoxCoordinates(
            # Верхние точки (86.65% - 94.17% по x, 14.11% - 14.60% по y)
            top_left_x=width * 0.8665,
            top_left_y=height * 0.1411,
            top_right_x=width * 0.9417,
            top_right_y=height * 0.1460,
            # Нижние точки (87.62% - 93.45% по x, 16.69% - 16.81% по y)
            bottom_left_x=width * 0.8762,
            bottom_left_y=height * 0.1669,
            bottom_right_x=width * 0.9345,
            bottom_right_y=height * 0.1681
        )

class ViewportLoader:
    @staticmethod
    def get_latest_trace() -> dict:
        try:
            # Находим последнюю trace директорию
            trace_pattern = "./recordings/tracer/trace_*"
            trace_dirs = glob.glob(trace_pattern)
            if not trace_dirs:
                logger.debug("Используются стандартные размеры viewport: height=815, width=412 (trace директории не найдены)")
                return {}
                
            latest_dir = max(trace_dirs, key=os.path.getctime)
            json_file = Path(latest_dir) / "interactions.json"
            
            if not json_file.exists():
                logger.debug("Используются стандартные размеры viewport: height=815, width=412 (файл interactions.json не найден)")
                return {}
                
            with open(json_file, 'r') as f:
                data = json.load(f)
                for event in reversed(data):
                    if "webAppState" in event:
                        height = event["webAppState"].get("viewportHeight", 815)
                        width = event["webAppState"].get("viewportStableWidth", 412)
                        logger.debug(f"Загружены размеры viewport из trace: height={height}, width={width}")
                        return {
                            "height": height,
                            "width": width
                        }
                logger.debug("Используются стандартные размеры viewport: height=815, width=412 (webAppState не найден в данных)")
                return {}
        except Exception as e:
            logger.error(f"Error loading viewport config: {e}")
            logger.debug("Используются стандартные размеры viewport: height=815, width=412 (ошибка загрузки конфигурации)")
            return {}

class ScreenZoneManager:
    """Менеджер зон экрана"""
    def __init__(self, viewport: ViewportConfig):
        self.viewport = viewport
        self.zones = self._initialize_zones()

    def _initialize_zones(self) -> Dict[str, List[BoxCoordinates]]:
        """Инициализация зон экрана с корректными прямоугольными областями"""
        width = self.viewport.width
        height = self.viewport.height
        
        # Количество горизонтальных зон
        HORIZONTAL_ZONES = 3
        
        zones = {
            'top': [BoxCoordinates(
                # Верхние точки (0-100% width, 0% height)
                top_left_x=0,
                top_left_y=0,
                top_right_x=width,
                top_right_y=0,
                # Нижние точки (0-100% width, 33.33% height)
                bottom_left_x=0,
                bottom_left_y=height / HORIZONTAL_ZONES,
                bottom_right_x=width,
                bottom_right_y=height / HORIZONTAL_ZONES
            )],
            'middle': [BoxCoordinates(
                # Верхние точки (0-100% width, 33.33% height)
                top_left_x=0,
                top_left_y=height / HORIZONTAL_ZONES,
                top_right_x=width,
                top_right_y=height / HORIZONTAL_ZONES,
                # Нижние точки (0-100% width, 66.67% height)
                bottom_left_x=0,
                bottom_left_y=2 * height / HORIZONTAL_ZONES,
                bottom_right_x=width,
                bottom_right_y=2 * height / HORIZONTAL_ZONES
            )],
            'bottom': [BoxCoordinates(
                # Верхние точки (0-100% width, 66.67% height)
                top_left_x=0,
                top_left_y=2 * height / HORIZONTAL_ZONES,
                top_right_x=width,
                top_right_y=2 * height / HORIZONTAL_ZONES,
                # Нижние точки (0-100% width, 100% height)
                bottom_left_x=0,
                bottom_left_y=height,
                bottom_right_x=width,
                bottom_right_y=height
            )]
        }
        
        return zones

@dataclass
class GameObjects:
    """Игровые объекты с динамическими координатами"""

    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
        
    def __init__(self):
        if GameObjects._instance is not None:
            return
            
        self.viewport = ViewportConfig(**ViewportLoader.get_latest_trace())
        self.zone_manager = ScreenZoneManager(self.viewport)
        self.initialize_box_objects()

    @staticmethod
    def get_random_point_in_area(coordinates: BoxCoordinates) -> Optional[Tuple[float, float]]:
        """Получение случайной точки внутри четырехугольной области"""

        try:
            if not isinstance(coordinates, BoxCoordinates):
                logger.error(f"Некорректный тип координат: {type(coordinates)}")
                return None

            # Определяем четыре угла четырехугольника
            top_left = (coordinates.top_left_x, coordinates.top_left_y)
            top_right = (coordinates.top_right_x, coordinates.top_right_y)
            bottom_right = (coordinates.bottom_right_x, coordinates.bottom_right_y)
            bottom_left = (coordinates.bottom_left_x, coordinates.bottom_left_y)

            # Разбиваем четырехугольник на два треугольника
            triangles = [
                [top_left, top_right, bottom_right],
                [top_left, bottom_left, bottom_right]
            ]

            # Выбираем случайный треугольник
            triangle = random.choice(triangles)

            # Генерируем случайные барицентрические координаты
            r1 = random.random()
            r2 = random.random()

            # Обеспечиваем, чтобы точка была внутри треугольника
            if r1 + r2 > 1:
                r1 = 1 - r1
                r2 = 1 - r2

            a_x, a_y = triangle[0]
            b_x, b_y = triangle[1]
            c_x, c_y = triangle[2]

            # Вычисляем координаты случайной точки
            x = a_x + r1 * (b_x - a_x) + r2 * (c_x - a_x)
            y = a_y + r1 * (b_y - a_y) + r2 * (c_y - a_y)

            return (x, y)

        except Exception as e:
            logger.error(f"Ошибка при получении случайной точки: {e}")
            return None

    
    def initialize_box_objects(self):
        """Инициализация базовых box объектов"""
        box_storage.add_object('chest', self.get_default_chest_area())
        box_storage.add_object('chest_numbers', self.get_default_chest_area_numbers())
        box_storage.add_object('autosell', self.get_default_autosell_area())
        box_storage.add_object('autosell_checkbox', self.get_default_autosell_checkbox_area())
        box_storage.add_object('equip_button', self.get_default_equip_area())
        box_storage.add_object('sell_button', self.get_default_sell_area())
        box_storage.add_object('power_area', self.get_default_power_area())
        box_storage.add_object('auto_equip_button', self.get_default_auto_equip_button())
        box_storage.add_object('level_and_stats_button', self.get_default_level_and_stats_area())
        box_storage.add_object('boss_button', self.get_default_boss_button())
        box_storage.add_object('auto_skill_button_click', self.get_auto_skill_button_click())
        box_storage.add_object('auto_skill_button_area', self.get_auto_skill_button_area())
        box_storage.add_object('task_button', self.get_default_task_button())
        box_storage.add_object('dayli_task_button', self.get_default_dayli_task_button())
        box_storage.add_object('daily_task_rewards_button', self.get_default_daily_task_rewards_button())

    # Функция расширения области для нахождения объектов
    def expand_area(self, area: BoxCoordinates, expand_percent: float = 0.1) -> BoxCoordinates:
        """
        Расширяет область, расширяя её границы на заданный процент,
        с проверкой выхода за границы viewport.

        Args:
            area: Исходная область
            expand_percent: Процент расширения (0.1 = 10%)

        Returns:
            BoxCoordinates: Расширенная область
        """
        # Собираем все x и y координаты
        x_coords = [area.top_left_x, area.top_right_x, area.bottom_right_x, area.bottom_left_x]
        y_coords = [area.top_left_y, area.top_right_y, area.bottom_right_y, area.bottom_left_y]

        # Находим минимальные и максимальные координаты
        x_min = min(x_coords)
        x_max = max(x_coords)
        y_min = min(y_coords)
        y_max = max(y_coords)

        # Вычисляем ширину и высоту
        width = x_max - x_min
        height = y_max - y_min

        # Вычисляем величину расширения
        dx = width * expand_percent
        dy = height * expand_percent

        # Новые координаты с проверкой границ viewport
        new_x_min = max(0, x_min - dx)
        new_x_max = min(self.viewport.width, x_max + dx)
        new_y_min = max(0, y_min - dy)
        new_y_max = min(self.viewport.height, y_max + dy)

        # Обновляем координаты
        expanded_area = BoxCoordinates(
            top_left_x=new_x_min,
            top_left_y=new_y_min,
            top_right_x=new_x_max,
            top_right_y=new_y_min,
            bottom_right_x=new_x_max,
            bottom_right_y=new_y_max,
            bottom_left_x=new_x_min,
            bottom_left_y=new_y_max
        )

        # Логирование для отладки
        logger.debug(
            f"Расширение области: original=({x_min},{y_min},{x_max},{y_max}), expanded=({new_x_min}, {new_y_min}, {new_x_max}, {new_y_max})"
        )

        return expanded_area



    def get_default_power_area(self) -> BoxCoordinates:
        """Область показателя силы"""
        width = self.viewport.width
        height = self.viewport.height
        
        return BoxCoordinates(
            # Верхние точки (63.35% - 91.02% по x, 63.07% - 57.30% по y)
            top_left_x=width * 0.6335,
            top_left_y=height * 0.5730,
            top_right_x=width * 0.9296,
            top_right_y=height * 0.5730,
            # Нижние точки (63.59% - 92.96% по x, 68.59% - 65.40% по y)
            bottom_left_x=width * 0.6335,
            bottom_left_y=height * 0.6859,
            bottom_right_x=width * 0.9296,
            bottom_right_y=height * 0.6859
        )

    def get_default_chest_area(self) -> BoxCoordinates:
        """Область сундука в процентах от размеров viewport"""
        width = self.viewport.width
        height = self.viewport.height
        
        return BoxCoordinates(
            # Верхние точки (42.72% - 58.01% по x, 87.24% по y)
            top_left_x=width * 0.4272,
            top_left_y=height * 0.8724,
            top_right_x=width * 0.5801,
            top_right_y=height * 0.8724,
            # Нижние точки (42.72% - 58.01% по x, 93.25% - 93.61% по y)
            bottom_left_x=width * 0.4272,
            bottom_left_y=height * 0.9325,
            bottom_right_x=width * 0.5801,
            bottom_right_y=height * 0.9361
        )

    def get_default_chest_area_numbers(self) -> BoxCoordinates:
        """Область сундука в процентах от размеров viewport для количества сундуков"""
        width = self.viewport.width
        height = self.viewport.height
        
        return BoxCoordinates(
            # Верхние точки (33.69% - 59.96% по x, 78.77% по y)
            top_left_x=width * 0.3369,
            top_left_y=height * 0.7877,
            top_right_x=width * 0.5996,
            top_right_y=height * 0.7877,
            # Нижние точки (33.69% - 59.96% по x, 100% по y)
            bottom_left_x=width * 0.3369,
            bottom_left_y=height * 1.0,
            bottom_right_x=width * 0.5996,
            bottom_right_y=height * 1.0
        )

    def get_default_autosell_area(self) -> BoxCoordinates:
        """Область кнопки автопродажи"""
        width = self.viewport.width
        height = self.viewport.height
        
        return BoxCoordinates(
            # Верхние точки (56.80% - 63.11% по x, 84.05% по y)
            top_left_x=width * 0.5680,
            top_left_y=height * 0.8405,
            top_right_x=width * 0.6311,
            top_right_y=height * 0.8405,
            # Нижние точки (57.04% - 62.14% по x, 86.26% - 85.89% по y)
            bottom_left_x=width * 0.5704,
            bottom_left_y=height * 0.8626,
            bottom_right_x=width * 0.6214,
            bottom_right_y=height * 0.8589
        )
        
    def get_default_autosell_checkbox_area(self) -> BoxCoordinates:
        """Область чекбокса автопродажи"""
        width = self.viewport.width
        height = self.viewport.height
        
        return BoxCoordinates(
            # Верхние точки (55.10% - 87.14% по x, 83.80% - 82.33% по y)
            top_left_x=width * 0.5510,
            top_left_y=height * 0.8380,
            top_right_x=width * 0.8714,
            top_right_y=height * 0.8233,
            # Нижние точки (53.88% - 87.14% по x, 86.50% - 85.89% по y)
            bottom_left_x=width * 0.5388,
            bottom_left_y=height * 0.8650,
            bottom_right_x=width * 0.8714,
            bottom_right_y=height * 0.8589
        )

    def get_default_equip_area(self) -> BoxCoordinates:
        """Область кнопки 'Оборудовать'"""
        width = self.viewport.width
        height = self.viewport.height
        
        return BoxCoordinates(
            # Верхние точки (56.07% - 86.89% по x, 87.12% - 86.63% по y)
            top_left_x=width * 0.5607,
            top_left_y=height * 0.8712,
            top_right_x=width * 0.8689,
            top_right_y=height * 0.8663,
            # Нижние точки (54.13% - 84.95% по x, 92.39% - 91.90% по y)
            bottom_left_x=width * 0.5413,
            bottom_left_y=height * 0.9239,
            bottom_right_x=width * 0.8495,
            bottom_right_y=height * 0.9190
        )

    def get_default_sell_area(self) -> BoxCoordinates:
        """Область кнопки 'Продать'"""
        width = self.viewport.width
        height = self.viewport.height
        
        return BoxCoordinates(
            # Верхние точки (14.81% - 45.15% по x, 86.50% - 86.38% по y)
            top_left_x=width * 0.1481,
            top_left_y=height * 0.8650,
            top_right_x=width * 0.4515,
            top_right_y=height * 0.8638,
            # Нижние точки (12.38% - 45.63% по x, 92.39% - 91.90% по y)
            bottom_left_x=width * 0.1238,
            bottom_left_y=height * 0.9239,
            bottom_right_x=width * 0.4563,
            bottom_right_y=height * 0.9190
        )

    # Пока не используется согласно логике 
    def get_default_auto_equip_button(self) -> BoxCoordinates:
        """Область кнопки 'Автооснащение'"""
        width = self.viewport.width
        height = self.viewport.height

        return BoxCoordinates(
            # Верхние точки (75.75% - 82.52% по x, 85.65% - 85.65% по y)
            top_left_x=width * 0.7575,
            top_left_y=height * 0.8565,
            top_right_x=width * 0.8252,
            top_right_y=height * 0.8565,
            # Нижние точки (75.75% - 82.52% по x, 87.97% - 87.97% по y)
            bottom_left_x=width * 0.7575,
            bottom_left_y=height * 0.8797,
            bottom_right_x=width * 0.8252,
            bottom_right_y=height * 0.8797
        )

    # Пока не используется согласно логике кнопки "авто" для сундуков
    def get_default_level_and_stats_area(self) -> BoxCoordinates:
        """Область кнопки 'Уровень и статистика'"""
        width = self.viewport.width
        height = self.viewport.height

        return BoxCoordinates(
            # Верхние точки (3.7% - 99.7% по x, 85.65% - 85.65% по y)
            top_left_x=width * 0.0364,
            top_left_y=height * 0.6331,
            top_right_x=width * 0.9805,
            top_right_y=height * 0.6331,
            # Нижние точки (3.7% - 99.7% по x, 87.97% - 87.97% по y)
            bottom_left_x=width * 0.0364,
            bottom_left_y=height * 0.6935,
            bottom_right_x=width * 0.9805,
            bottom_right_y=height * 0.6935
        )

    # Кнопка "Босс"
    def get_default_boss_button(self) -> BoxCoordinates:
        """Область кнопки 'Босс'"""
        width = self.viewport.width
        height = self.viewport.height

        return BoxCoordinates(
            # Верхние точки (46.1% - 54.6% по x, 49.1% по y)
            top_left_x=width * 0.4611,
            top_left_y=height * 0.4911,
            top_right_x=width * 0.5465,
            top_right_y=height * 0.4911,
            # Нижние точки (46.1% - 54.6% по x, 51.5% по y)
            bottom_left_x=width * 0.4611,
            bottom_left_y=height * 0.5151,
            bottom_right_x=width * 0.5465,
            bottom_right_y=height * 0.5151
        )

    # Кнопка клик "Автоскилл"
    def get_auto_skill_button_click(self) -> BoxCoordinates:
        """Область кнопки 'Автоскилл'"""
        width = self.viewport.width
        height = self.viewport.height   

        return BoxCoordinates(
            # Верхние точки (14.14% - 16.99% по x, 56.88% по y)
            top_left_x=width * 0.1414,
            top_left_y=height * 0.5688,
            top_right_x=width * 0.1699,
            top_right_y=height * 0.5688,
            # Нижние точки (14.14% - 16.99% по x, 59.59% по y)
            bottom_left_x=width * 0.1414,
            bottom_left_y=height * 0.5959,
            bottom_right_x=width * 0.1699,
            bottom_right_y=height * 0.5959
        )

    # Область кнопки 'Автоскилл' для скрина
    def get_auto_skill_button_area(self) -> BoxCoordinates:
        """Область кнопки 'Автоскилл'"""
        width = self.viewport.width
        height = self.viewport.height

        return BoxCoordinates(
            # Верхние точки (14.14% - 16.99% по x, 56.88% по y)
            top_left_x=width * 0.1212,
            top_left_y=height * 0.5454,
            top_right_x=width * 0.1688,
            top_right_y=height * 0.5454,
            # Нижние точки (14.14% - 16.99% по x, 59.59% по y)
            bottom_left_x=width * 0.1212,
            bottom_left_y=height * 0.6969,
            bottom_right_x=width * 0.1688,
            bottom_right_y=height * 0.6969
        )

    # Кнопка "Задание" 
    def get_default_task_button(self) -> BoxCoordinates:
        """Область кнопки 'Задание'"""
        width = self.viewport.width
        height = self.viewport.height   

        return BoxCoordinates(
            # Верхние точки (21.36% - 30.83% по x, 92.88% по y)
            top_left_x=width * 0.2136,
            top_left_y=height * 0.9288,
            top_right_x=width * 0.3083,
            top_right_y=height * 0.9288,
            # Нижние точки (21.36% - 30.83% по x, 96.33% по y)
            bottom_left_x=width * 0.2136,
            bottom_left_y=height * 0.9633,
            bottom_right_x=width * 0.3083,
            bottom_right_y=height * 0.9633
        )

    # Кнопка "Daily Task"
    def get_default_dayli_task_button(self) -> BoxCoordinates:
        """Область кнопки 'Daily Task'"""
        width = self.viewport.width
        height = self.viewport.height

        return BoxCoordinates(
            # Верхние точки (30.30% - 50.95% по x, 87.11% по y)
            top_left_x=width * 0.3030,
            top_left_y=height * 0.8711,
            top_right_x=width * 0.5095,
            top_right_y=height * 0.8711,
            # Нижние точки (30.30% - 50.95% по x, 89.60% по y) 
            bottom_left_x=width * 0.3030,
            bottom_left_y=height * 0.8960,
            bottom_right_x=width * 0.5095,
            bottom_right_y=height * 0.8960
        )

    # Кнопка "Получить награду" внутри Daily Task
    def get_default_daily_task_rewards_button(self) -> BoxCoordinates:
        """Область кнопки 'Получить награду'"""
        width = self.viewport.width
        height = self.viewport.height

        return BoxCoordinates(
            # Верхние точки (68.45% - 84.71% по x, 26.01% по y)
            top_left_x=width * 0.6845,
            top_left_y=height * 0.2601,
            top_right_x=width * 0.8471,
            top_right_y=height * 0.2601,
            # Нижние точки (68.45% - 84.71% по x, 29.69% по y)
            bottom_left_x=width * 0.6845,
            bottom_left_y=height * 0.2969,
            bottom_right_x=width * 0.8471,
            bottom_right_y=height * 0.2969
        )