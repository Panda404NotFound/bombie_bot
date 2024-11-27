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
import math

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
    def get_random_point_in_area(coordinates: BoxCoordinates) -> Tuple[float, float]:
        """
        Получение случайной точки внутри области путем анализа диапазонов координат.
        """
        try:
            # Проверка корректности входных данных
            if not isinstance(coordinates, BoxCoordinates):
                logger.error(f"Некорректный тип координат: {type(coordinates)}")
                return (0.5, 0.5)

            # Получаем все точки
            points = [
                (coordinates.top_left_x, coordinates.top_left_y),
                (coordinates.top_right_x, coordinates.top_right_y),
                (coordinates.bottom_right_x, coordinates.bottom_right_y),
                (coordinates.bottom_left_x, coordinates.bottom_left_y)
            ]

            # Получаем уникальные отсортированные значения X и Y
            x_values = sorted(set(p[0] for p in points))
            y_values = sorted(set(p[1] for p in points))

            def find_range_bounds(values):
                """
                Находит корректные границы диапазона, учитывая близость значений
                """
                if len(values) <= 2:
                    return min(values), max(values)
                    
                # Находим разницы между соседними значениями
                diffs = [values[i+1] - values[i] for i in range(len(values)-1)]
                min_diff = min(diffs)
                # Находим все индексы с минимальной разницей
                min_diff_indices = [i for i, d in enumerate(diffs) if d == min_diff]
                # Берем первый индекс
                min_diff_idx = min_diff_indices[0]
                
                # Получаем два ближайших значения
                close_values = [values[min_diff_idx], values[min_diff_idx + 1]]
                lower_bound = max(close_values)
                upper_bound = max(values)

                return lower_bound, upper_bound

            # Определяем корректные диапазоны для X и Y
            x_min, x_max = find_range_bounds(x_values)
            y_min, y_max = find_range_bounds(y_values)

            # Генерируем случайную точку внутри определенных границ
            random_x = random.uniform(x_min, x_max)
            random_y = random.uniform(y_min, y_max)

            logger.debug(f"Сгенерированная точка: ({random_x}, {random_y})")
            return (random_x, random_y)

        except Exception as e:
            logger.error(f"Ошибка при получении случайной точки: {e}")
            return (0.5, 0.5)


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

        # Вычисляем ширину и ��ысоту
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
        box_storage.add_object('invite_main_button', self.get_default_invite_main_button())
        box_storage.add_object('invite_friend_button', self.get_default_invite_friend_button())
        box_storage.add_object('invite_dayli_reward_button', self.get_default_invite_dayli_reward_button())
        box_storage.add_object('invite_dayli_reward_get_button', self.get_default_invite_dayli_reward_get_button())
        box_storage.add_object('back_button', self.get_default_back_button())
        box_storage.add_object('magazine_main_menu', self.get_default_magazine_button())
        box_storage.add_object('free_magazine_chest', self.get_default_magazine_free_chest())
        box_storage.add_object('kubok_free_rewards_area', self.get_default_kubok_free_rewards_area())
        box_storage.add_object('kubok_free_rewards_like', self.get_default_kubok_free_rewards_like())
        box_storage.add_object('message_free_rewards', self.get_default_message_free_rewards())


    # Область силы для сравнения внутри сундука
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

    # Область сундука для нажатия
    def get_default_chest_area(self) -> BoxCoordinates:
        """Область сундука в процентах от размеров viewport"""
        width = self.viewport.width
        height = self.viewport.height
        
        return BoxCoordinates(
            # Верхние точки (47.47% - 52.22% по x, 89.29% по y)
            top_left_x=width * 0.4847,
            top_left_y=height * 0.8629,
            top_right_x=width * 0.5022,
            top_right_y=height * 0.8629,
            # Нижние точки (47.47% - 52.22% по x, 91.75% по y)
            bottom_left_x=width * 0.4847,
            bottom_left_y=height * 0.8975,
            bottom_right_x=width * 0.5022,
            bottom_right_y=height * 0.8975
        )

    # Область сундука для определения количества сундуков 
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

    # Область кнопки автопродажи внутри сундука
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
            top_right_y=height * 0.8650,
            # Нижние точки (12.38% - 45.63% по x, 92.39% - 91.90% по y)
            bottom_left_x=width * 0.1481,
            bottom_left_y=height * 0.9229,
            bottom_right_x=width * 0.4515,
            bottom_right_y=height * 0.9229
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
    
    # Кнопка пригласить в главном меню
    def get_default_invite_main_button(self) -> BoxCoordinates:
        width = self.viewport.width
        height = self.viewport.height

        return BoxCoordinates(
            # Верхние точки (290/412 = 0.7038, 316/412 = 0.7670 по x, 758/815 = 0.9301 по y)
            top_left_x=width * 0.7038,
            top_left_y=height * 0.9301,
            top_right_x=width * 0.7670,
            top_right_y=height * 0.9301,
            # Нижние точки (290/412 = 0.7038, 316/412 = 0.7670 по x, 780/815 = 0.9571 по y)
            bottom_left_x=width * 0.7038,
            bottom_left_y=height * 0.9571,
            bottom_right_x=width * 0.7670,
            bottom_right_y=height * 0.9571
        )

    # Пригласить друга кнопка забрать сундук
    def get_default_invite_friend_button(self) -> BoxCoordinates:
        width = self.viewport.width
        height = self.viewport.height

        return BoxCoordinates(
            # Верхние точки (138/412 = 0.3350, 280/412 = 0.6796 по x, 717/815 = 0.8798 по y)
            top_left_x=width * 0.3350,
            top_left_y=height * 0.8798,
            top_right_x=width * 0.6796,
            top_right_y=height * 0.8798,
            # Нижние точки (138/412 = 0.3350, 280/412 = 0.6796 по x, 740/815 = 0.9080 по y)
            bottom_left_x=width * 0.3350,
            bottom_left_y=height * 0.9080,
            bottom_right_x=width * 0.6796,
            bottom_right_y=height * 0.9080
        )

    # Кнопка ежедневных заданий в Пригласить 
    def get_default_invite_dayli_reward_button(self) -> BoxCoordinates:
        width = self.viewport.width
        height = self.viewport.height

        return BoxCoordinates(
            # Верхние точки (245/412 = 0.5947, 370/412 = 0.8981 по x, 646/815 = 0.7926 по y)
            top_left_x=width * 0.5947,
            top_left_y=height * 0.7926,
            top_right_x=width * 0.8981,
            top_right_y=height * 0.7926,
            # Нижние точки (245/412 = 0.5947, 370/412 = 0.8981 по x, 668/815 = 0.8196 по y)
            bottom_left_x=width * 0.5947,
            bottom_left_y=height * 0.8196,
            bottom_right_x=width * 0.8981,
            bottom_right_y=height * 0.8196
        )

    # Кнопка получить в ежедневных заданиях в Пригласить 
    def get_default_invite_dayli_reward_get_button(self) -> BoxCoordinates:
        width = self.viewport.width
        height = self.viewport.height

        return BoxCoordinates(
            # Верхние точки (274/412 = 0.6650, 370/412 = 0.8981 по x, 646/815 = 0.7926 по y)
            top_left_x=width * 0.6650,
            top_left_y=height * 0.7926,
            top_right_x=width * 0.8981,
            top_right_y=height * 0.7926,
            # Нижние точки (274/412 = 0.6650, 370/412 = 0.8981 по x, 674/815 = 0.8270 по y)
            bottom_left_x=width * 0.6650,
            bottom_left_y=height * 0.8270,
            bottom_right_x=width * 0.8981,
            bottom_right_y=height * 0.8270
        )

    # Кнопка назад в меню 
    def get_default_back_button(self) -> BoxCoordinates:
        width = self.viewport.width
        height = self.viewport.height

        return BoxCoordinates(
            # Верхние точки (26/412 = 0.0631, 50/412 = 0.1214 по x, 65/815 = 0.0798 по y)
            top_left_x=width * 0.0631,
            top_left_y=height * 0.0798,
            top_right_x=width * 0.1214,
            top_right_y=height * 0.0798,
            # Нижние точки (26/412 = 0.0631, 46/412 = 0.1117 по x, 75/815 = 0.0920 по y)
            bottom_left_x=width * 0.0631,
            bottom_left_y=height * 0.0920,
            bottom_right_x=width * 0.1117,
            bottom_right_y=height * 0.0920
        )

    # Кнопка магазина на главном меню
    def get_default_magazine_button(self) -> BoxCoordinates:
        width = self.viewport.width
        height = self.viewport.height

        return BoxCoordinates(
            # Верхние точки (350/412 = 0.8495, 390/412 = 0.9466 по x, 750/815 = 0.9202 по y)
            top_left_x=width * 0.8495,
            top_left_y=height * 0.9202,
            top_right_x=width * 0.9466,
            top_right_y=height * 0.9202,
            # Нижние точки (350/412 = 0.8495, 390/412 = 0.9466 по x, 780/815 = 0.9571 по y)
            bottom_left_x=width * 0.8495,
            bottom_left_y=height * 0.9571,
            bottom_right_x=width * 0.9466,
            bottom_right_y=height * 0.9571
        )

    # Кнопка получить сундук внутри магазина халявный 
    def get_default_magazine_free_chest(self) -> BoxCoordinates:
        width = self.viewport.width
        height = self.viewport.height

        return BoxCoordinates(
            # Верхние точки (52/412 = 0.1262, 125/412 = 0.3034 по x, 305/815 = 0.3742 по y)
            top_left_x=width * 0.1262,
            top_left_y=height * 0.3742,
            top_right_x=width * 0.3034,
            top_right_y=height * 0.3742,
            # Нижние точки (52/412 = 0.1262, 125/412 = 0.3034 по x, 315/815 = 0.3865 по y)
            bottom_left_x=width * 0.1262,
            bottom_left_y=height * 0.3865,
            bottom_right_x=width * 0.3034,
            bottom_right_y=height * 0.3865
        )

    # Область кнопки "Кубок" слева сверху
    def get_default_kubok_free_rewards_area(self) -> BoxCoordinates:
        width = self.viewport.width
        height = self.viewport.height

        return BoxCoordinates(
            # Верхние точки (25/412 = 0.0607, 50/412 = 0.1214 по x, 102/815 = 0.1252 по y)
            top_left_x=width * 0.0607,
            top_left_y=height * 0.1252,
            top_right_x=width * 0.1214,
            top_right_y=height * 0.1252,
            # Нижние точки (25/412 = 0.0607, 50/412 = 0.1214 по x, 128/815 = 0.1571 по y)
            bottom_left_x=width * 0.0607,
            bottom_left_y=height * 0.1571,
            bottom_right_x=width * 0.1214,
            bottom_right_y=height * 0.1571
        )

    # Область кнопки "Лайк" в кубке 
    def get_default_kubok_free_rewards_like(self) -> BoxCoordinates:
        width = self.viewport.width
        height = self.viewport.height

        return BoxCoordinates(
            # Верхние точки (240/412 = 0.5825, 250/412 = 0.6068 по x, 195/815 = 0.2393 по y)
            top_left_x=width * 0.5825,
            top_left_y=height * 0.2393,
            top_right_x=width * 0.6068,
            top_right_y=height * 0.2393,
            # Нижние точки (240/412 = 0.5825, 250/412 = 0.6068 по x, 200/815 = 0.2454 по y)
            bottom_left_x=width * 0.5825,
            bottom_left_y=height * 0.2454,
            bottom_right_x=width * 0.6068,
            bottom_right_y=height * 0.2454
        )

    # Кнопка собрать вознагражденя в конверте
    def get_default_message_free_rewards(self) -> BoxCoordinates:
        width = self.viewport.width
        height = self.viewport.height
        
        return BoxCoordinates(
            # Верхние точки (254/412 = 0.6165, 335/412 = 0.8131 по x, 642/815 = 0.7877 по y)
            top_left_x=width * 0.6165,
            top_left_y=height * 0.7877,
            top_right_x=width * 0.8131, 
            top_right_y=height * 0.7877,
            # Нижние точки (254/412 = 0.6165, 335/412 = 0.8131 по x, 666/815 = 0.8172 по y)
            bottom_left_x=width * 0.6165,
            bottom_left_y=height * 0.8172,
            bottom_right_x=width * 0.8131,
            bottom_right_y=height * 0.8172
        )