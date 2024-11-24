# bombie_objects.py
import numpy as np
import easyocr
import random 
import io 
from PIL import Image
import asyncio
from loguru import logger
from typing import Dict, Tuple, Optional
from .cordination_module import GameObjects, ViewportConfig
from .data_class import BoxCoordinates, BoxObject, GlobalBoxStorage, box_storage
from .ocr_manager import OCRManager

class ScreenManager:
    def __init__(self, page, game_objects=None):
        self.page = page
        self.reader = OCRManager().get_reader
        self.game_objects = game_objects if game_objects else GameObjects()
        self.viewport = self.game_objects.viewport

    async def take_screenshot(self, area: Optional[BoxCoordinates] = None) -> Optional[np.ndarray]:
        try:
            viewport_height = self.viewport.height
            viewport_width = self.viewport.width
            
            logger.debug(f"Ожидаемые размеры viewport: {viewport_width}x{viewport_height}")
            
            # Получаем скриншот как bytes
            screenshot_bytes = await self.page.screenshot(
                type='png',
                full_page=False,
                scale='css' 
            )
            
            # Конвертируем bytes в numpy array через PIL
            # (сохраняем текущий пайплайн обработки изображения)
            image = Image.open(io.BytesIO(screenshot_bytes))
            screenshot_array = np.array(image)
            
            # Если указана область, обрезаем изображение
            if area:
                x1 = max(0, min(area.top_left_x, area.bottom_left_x))
                y1 = max(0, min(area.top_left_y, area.top_right_y))
                x2 = max(0, min(area.top_right_x, area.bottom_right_x))
                y2 = max(0, min(area.bottom_left_y, area.bottom_right_y))
                
                logger.debug(f"Обрезка области: x1={x1}, y1={y1}, x2={x2}, y2={y2}")
                screenshot_array = screenshot_array[int(y1):int(y2), int(x1):int(x2)]
            
            logger.debug(f"Итоговый размер скриншота: {screenshot_array.shape}")
            return screenshot_array
            
        except Exception as e:
            logger.error(f"Ошибка создания скриншота: {e}")
            return None

    async def get_text_from_area(self, image: np.ndarray, area: BoxCoordinates) -> str:
        try:
            # Определяем границы области для OCR
            x1 = min(area.top_left_x, area.bottom_left_x)
            y1 = min(area.top_left_y, area.top_right_y)
            x2 = max(area.top_right_x, area.bottom_right_x)
            y2 = max(area.bottom_left_y, area.bottom_right_y)
            
            # Сначала делаем полный OCR всего изображения
            logger.debug(f"Анализ текста в области: x1={x1}, y1={y1}, x2={x2}, y2={y2}")
            
            full_results = self.reader.readtext(image)
            logger.debug(f"Найдено {len(full_results)} текстовых элементов на изображении")
            
            valid_results = []
            for (bbox, text, prob) in full_results:
                # Получаем координаты текста
                (text_x1, text_y1), (text_x2, text_y2) = bbox[0], bbox[2]
                
                # Проверяем, находится ли текст в нужной области
                if area.contains_point(text_x1, text_y1) and area.contains_point(text_x2, text_y2):
                    logger.debug(f"Найден текст в нужной области: '{text}' с вероятностью {prob:.2f}")
                    valid_results.append((text, prob))
            
            if valid_results:
                # Выбираем результат с наибольшей вероятностью
                best_result = max(valid_results, key=lambda x: x[1])
                logger.info(f"Выбран лучший результат: '{best_result[0]}' с вероятностью {best_result[1]:.2f}")
                return best_result[0]
                
            logger.warning("В указанной области текст не найден")
            return ""
            
        except Exception as e:
            logger.error(f"Ошибка OCR: {e}")
            logger.debug(f"Размер входного изображения: {image.shape if image is not None else 'None'}")
            return ""