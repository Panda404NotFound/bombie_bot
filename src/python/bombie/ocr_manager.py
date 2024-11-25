import torch
import cv2
from loguru import logger
from dataclasses import dataclass, field
import easyocr
from .data_class import BoxCoordinates, BoxObject, GlobalBoxStorage
from typing import Optional, Tuple
import numpy as np
import certifi
import ssl
import urllib.request

class OCRManager:
    _instance = None
    _reader = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            try:
                # Настройки для безопасной загрузки моделей
                torch.backends.cudnn.enabled = False
                torch.set_grad_enabled(False)
                
                # Настройка безопасного SSL-контекста
                ssl_context = ssl.create_default_context(
                    purpose=ssl.Purpose.SERVER_AUTH,
                    cafile=certifi.where()
                )
                
                # Создаем безопасный opener для urllib
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=ssl_context)
                )
                urllib.request.install_opener(opener)
                
                # Инициализация reader с безопасными настройками
                cls._reader = easyocr.Reader(
                    ['ru', 'en'],  # Поддерживаемые языки
                    model_storage_directory='./models',  # Директория для хранения моделей
                    download_enabled=True,  # Разрешить загрузку моделей
                    detector=True,  # Использовать детектор текста
                    recognizer=True,  # Использовать распознаватель текста
                    verbose=False,  # Отключить подробный вывод
                    gpu=False,  # Не использовать GPU
                    quantize=True,  # Использовать квантизацию для оптимизации памяти
                )
                logger.info("OCR Manager успешно инициализирован")
            except Exception as e:
                logger.error(f"Ошибка инициализации OCR: {e}")
                raise RuntimeError("Не удалось инициализировать OCR") from e
        return cls._instance

    @property
    def get_reader(self):
        if not self._reader:
            logger.error("OCR Reader не инициализирован")
            raise RuntimeError("OCR Reader не инициализирован")
        logger.debug("OCR Reader успешно получен")
        return self._reader

    def __del__(self):
        # Очистка ресурсов при удалении
        if self._reader:
            try:
                logger.debug("Очистка ресурсов OCR Reader")
                del self._reader
                torch.cuda.empty_cache()
                logger.debug("Ресурсы OCR Reader успешно очищены")
            except Exception as e:
                logger.error(f"Ошибка при очистке ресурсов OCR Reader: {e}")
                pass

@dataclass
class OCRCoordinator:
    """
    - Координация между OCR и PIL/numpy для определения координат
    - Вывод всех найденных текстов в get_text_from_image
    - Проверка наличия текста в зоне (не совсем удачная реализация)
    
    """

    @staticmethod
    def preprocess_image(image: np.ndarray) -> np.ndarray:
        """
        Предварительная обработка изображения для улучшения распознавания цифр
        """
        try:
            # Увеличение размера
            image = cv2.resize(image, None, fx=1.5, fy=1.5, 
                            interpolation=cv2.INTER_CUBIC)
            
            # Преобразование в оттенки серого
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Адаптивная бинаризация
            binary = cv2.adaptiveThreshold(gray, 255, 
                                        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY, 11, 2)
            
            # Удаление шума
            denoised = cv2.fastNlMeansDenoising(binary)
            
            return denoised
        except Exception as e:
            logger.error(f"Ошибка предобработки изображения: {e}")
            return image
    
    @staticmethod
    def get_numbers_from_image(image: np.ndarray) -> list[str]:
        """
        Оптимизированное получение текста с акцентом на цифры
        """
        try:
            reader = OCRManager().get_reader
            
            # Параметры для readtext метода
            results = reader.readtext(
                image,
                decoder='beamsearch',  # Использовать beam search для лучшего распознавания
                beamWidth=10,  # Увеличенная ширина луча для более точного поиска
                batch_size=1,  # Размер пакета для обработки
                allowlist='0123456789.',  # Разрешить только цифры и точку
                detail=1,  # Возвращать детальную информацию
                min_size=10,  # Минимальный размер текстового блока
                text_threshold=0.3,  # Порог уверенности для текста
                low_text=0.3,  # Нижний порог для слабого текста
                link_threshold=0.3,  # Порог связности текстовых блоков
                canvas_size=1280,  # Максимальный размер изображения
                mag_ratio=1.5,  # Коэффициент увеличения для мелкого текста
                slope_ths=0.2,  # Максимальный наклон для объединения блоков
                ycenter_ths=0.7,  # Порог центрирования по Y
                height_ths=0.7,  # Порог различия высоты блоков
                width_ths=0.7,  # Порог расстояния между блоками
                add_margin=0.15,  # Дополнительные отступы вокруг текста
            )
            
            logger.info(f"Найденные тексты: {results}")
            
            # Фильтрация и очистка результатов
            detected_texts = []
            for bbox, text, conf in results:
                # Оставляем только цифры и точки
                cleaned_text = ''.join(c for c in text if c.isdigit() or c == '.')
                # Проверяем уверенность распознавания
                if cleaned_text and conf > 0.15:
                    detected_texts.append(cleaned_text)

            logger.info(f"Обработанные цифровые значения: {detected_texts}")

            # Если в списке есть "0", возвращаем только его
            if "0" in detected_texts:
                detected_texts = ["0"]
                    
            logger.info(f"Возвращаемые цифровые значения: {detected_texts}")
            
            # Если список пустой, возвращаем 1
            if not detected_texts:
                logger.info("Список пустой, возвращаем значение по умолчанию: ['1']")
                return ["1"]
            
            return detected_texts
                
        except Exception as e:
            logger.error(f"Ошибка распознавания текста: {e}")
            return ["1"]  # Также возвращаем 1 в случае ошибки

    @staticmethod
    def check_text_in_area(image: np.ndarray, 
                          texts: str | list[str], 
                          zone: Optional[BoxCoordinates] = None, 
                          threshold: float = 0.85) -> Tuple[bool, float]:
        """
        Проверяет наличие текстов в указанной зоне или во всем изображении
        
        Args:
            image: Изображение в формате numpy array
            texts: Искомый текст или список текстов
            zone: Опциональная зона поиска. Если None, используется все изображение
            threshold: Минимальный порог вероятности распознавания
        """
        logger.debug(f"Поиск текстов{' в зоне: ' + str(zone) if zone else ' во всем изображении'}")
        
        try:
            # Валидация входного изображения
            if image is None or image.size == 0:
                logger.warning("Получено пустое изображение")
                return False, 0.0

            # Определяем область поиска
            if zone is not None:
                # Валидация координат
                if (zone.bottom_right_y <= zone.top_left_y or 
                    zone.bottom_right_x <= zone.top_left_x):
                    logger.warning("Некорректные координаты зоны поиска")
                    return False, 0.0

                # Проверка выхода за границы изображения
                height, width = image.shape[:2]
                top = max(0, min(int(zone.top_left_y), height-1))
                bottom = max(0, min(int(zone.bottom_right_y), height))
                left = max(0, min(int(zone.top_left_x), width-1))
                right = max(0, min(int(zone.bottom_right_x), width))

                # Проверка размеров области после коррекции
                if right <= left or bottom <= top:
                    logger.warning("Область поиска имеет нулевой размер после коррекции координат")
                    return False, 0.0

                try:
                    image_to_process = image[top:bottom, left:right]
                except Exception as crop_error:
                    logger.error(f"Ошибка при обрезке изображения: {crop_error}")
                    return False, 0.0
            else:
                # Используем все изображение
                image_to_process = image

            if image_to_process.size == 0:
                logger.warning("Получена пустая область для обработки")
                return False, 0.0

            # Дальнейшая обработка текста
            reader = OCRManager().get_reader
            texts_to_check = [texts] if isinstance(texts, str) else texts
            
            results = reader.readtext(image_to_process)
            logger.debug(f"Найденные тексты: {results}")
            
            found_matches = []
            total_prob = 0
            
            for _, detected_text, prob in results:
                for search_text in texts_to_check:
                    if search_text.lower() in detected_text.lower() and prob >= threshold:
                        found_matches.append({
                            'text': search_text,
                            'prob': prob
                        })
                        total_prob += prob
                        logger.info(f"Найден текст '{search_text}' с вероятностью {prob:.2f}")
            
            if found_matches:
                avg_prob = total_prob / len(found_matches)
                return True, avg_prob
                
            logger.debug(f"Тексты {texts_to_check} не найдены")
            return False, 0.0
            
        except cv2.error as cv_err:
            logger.warning(f"OpenCV ошибка: {cv_err}")
            return False, 0.0
        except Exception as e:
            logger.error(f"Ошибка поиска текста: {e}")
            return False, 0.0