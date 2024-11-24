# cv_manager.py
import cv2
import numpy as np
from loguru import logger
from typing import Optional, Tuple, List
from pathlib import Path

class CVManager:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CVManager, cls).__new__(cls)
        return cls._instance

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        
    def cleanup(self):
        """Очистка ресурсов"""
        self._templates.clear()
        cv2.destroyAllWindows()
        
    def __init__(self):
        if not CVManager._initialized:
            self._templates = {}
            # Ищем templates директорию, начиная с текущей директории и поднимаясь вверх
            current_dir = Path(__file__).parent
            self.templates_dir = None
            
            # Поиск templates директории
            while current_dir != current_dir.parent:
                templates_path = current_dir / "templates"
                if templates_path.exists() and templates_path.is_dir():
                    self.templates_dir = templates_path
                    break
                current_dir = current_dir.parent
                
            if self.templates_dir is None:
                logger.error("Директория templates не найдена")
                raise RuntimeError("Не удалось найти директорию templates")
                
            logger.debug(f"Найдена директория templates: {self.templates_dir}")
            self.load_checkbox_templates()
            CVManager._initialized = True

    def load_checkbox_templates(self):
        """Загрузка шаблонов чекбоксов"""
        try:
            template_paths = {
                'true_autosell_set': None,
                'false_autosell_set': None,
                'true_power_chest': None,
                'false_power_chest': None,
                'false_auto_skill_button': None,
                'true_auto_skill_button': None,
                'true_task_action': None,
                'false_task_action': None
            }
            
            # Поиск файлов шаблонов
            for ext in ['.png', '.jpg', '.jpeg']:
                for name in template_paths.keys():
                    matches = list(self.templates_dir.rglob(f"*{name}*{ext}"))
                    if matches and not template_paths[name]:
                        template_paths[name] = matches[0]
            
            # Проверка наличия всех шаблонов
            missing = [name for name, path in template_paths.items() if not path]
            if missing:
                raise FileNotFoundError(f"Не найдены шаблоны: {', '.join(missing)}")
                
            # Загрузка шаблонов с проверкой
            self.true_autosell_template = cv2.imread(str(template_paths['true_autosell_set']), cv2.IMREAD_GRAYSCALE)
            self.false_autosell_template = cv2.imread(str(template_paths['false_autosell_set']), cv2.IMREAD_GRAYSCALE)
            self.true_power_template = cv2.imread(str(template_paths['true_power_chest']), cv2.IMREAD_GRAYSCALE)
            self.false_power_template = cv2.imread(str(template_paths['false_power_chest']), cv2.IMREAD_GRAYSCALE)
            self.false_auto_skill_template = cv2.imread(str(template_paths['false_auto_skill_button']), cv2.IMREAD_GRAYSCALE)
            self.true_auto_skill_template = cv2.imread(str(template_paths['true_auto_skill_button']), cv2.IMREAD_GRAYSCALE)
            self.true_daily_task_rewards_template = cv2.imread(str(template_paths['true_task_action']), cv2.IMREAD_GRAYSCALE)
            self.false_daily_task_rewards_template = cv2.imread(str(template_paths['false_task_action']), cv2.IMREAD_GRAYSCALE)
            
            # Проверка загруженных шаблонов
            templates = {
                'true_autosell_set': self.true_autosell_template,
                'false_autosell_set': self.false_autosell_template,
                'true_power_chest': self.true_power_template,
                'false_power_chest': self.false_power_template,
                'false_auto_skill_button': self.false_auto_skill_template,
                'true_auto_skill_button': self.true_auto_skill_template,
                'true_task_action': self.true_daily_task_rewards_template,
                'false_task_action': self.false_daily_task_rewards_template
            }
            
            failed = [name for name, template in templates.items() if template is None]
            if failed:
                raise RuntimeError(f"Не удалось загрузить шаблоны: {', '.join(failed)}")
                
            logger.info("Все шаблоны успешно загружены")
            logger.debug(f"Директория шаблонов: {self.templates_dir}")
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке шаблонов: {e}")
            raise

    # Функция для масштабирования шаблонов
    def scale_template_if_needed(self, image: np.ndarray, template1: np.ndarray, 
                           template2: np.ndarray, scale_factor: float = 0.4) -> Tuple[np.ndarray, np.ndarray]:
        """
        Масштабирует шаблоны если входное изображение меньше шаблона.
        
        Args:
            image: Входное изображение
            template1: Первый шаблон для сравнения
            template2: Второй шаблон для сравнения
            scale_factor: Коэффициент масштабирования (по умолчанию 0.4)
            
        Returns:
            Tuple[np.ndarray, np.ndarray]: Масштабированные шаблоны (template1, template2)
        """
        img_h, img_w = image.shape[:2]  # Поддержка как grayscale, так и цветных изображений
        templ_h, templ_w = template1.shape[:2]
        
        if img_h < templ_h or img_w < templ_w:
            logger.debug(f"Масштабирование шаблона: img_h={img_h}, img_w={img_w}, templ_h={templ_h}, templ_w={templ_w}")
            scale = min(img_h/templ_h, img_w/templ_w) * scale_factor
            new_size = (int(templ_w * scale), int(templ_h * scale))
            scaled_template1 = cv2.resize(template1, new_size)
            scaled_template2 = cv2.resize(template2, new_size)
            return scaled_template1, scaled_template2
        
        logger.debug(f"Шаблоны не масштабируются: img_h={img_h}, img_w={img_w}, templ_h={templ_h}, templ_w={templ_w}")
        return template1, template2

    # Основная функция для определения состояния чекбокса автопродажи
    def find_autosell_checkbox(self, image: np.ndarray) -> bool:
        """Определение состояния чекбокса автопродажи"""
            
        try:
            # Конвертируем в grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
                
            # Проверяем совпадение с обоими шаблонами
            true_result = cv2.matchTemplate(gray, self.true_autosell_template, cv2.TM_CCOEFF_NORMED)
            false_result = cv2.matchTemplate(gray, self.false_autosell_template, cv2.TM_CCOEFF_NORMED)
            
            true_val = np.max(true_result)
            false_val = np.max(false_result)
            
            logger.debug(f"Совпадение автопродажи: true={true_val:.3f}, false={false_val:.3f}")
            
            # Определяем состояние по лучшему совпадению
            result = true_val > false_val
            
            logger.debug(f"Результат проверки чекбокса: {result}")
            
            return result
                
        except Exception as e:
            logger.error(f"Ошибка при определении состояния чекбокса: {e}")
            return False

    # Основная функция для определения состояния индикатора силы с помощью цветовых характеристик
    def find_power_checkbox(self, image: np.ndarray) -> bool:
        """Определение состояния индикатора силы с учетом цветовых характеристик"""

        try:
            # Конвертируем в HSV для лучшего определения цветов
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # Определяем диапазоны для зеленого цвета (положительное изменение)
            lower_green = np.array([40, 50, 50])
            upper_green = np.array([80, 255, 255])
            
            # Определяем диапазон для красного цвета (отрицательное изменение)
            lower_red1 = np.array([0, 50, 50])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([170, 50, 50])
            upper_red2 = np.array([180, 255, 255])
            
            # Создаем маски
            mask_green = cv2.inRange(hsv, lower_green, upper_green)
            mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
            
            # Объединяем маски для красного цвета
            mask_red = cv2.bitwise_or(mask_red1, mask_red2)
            
            # Подсчитываем пиксели
            green_pixels = cv2.countNonZero(mask_green)
            red_pixels = cv2.countNonZero(mask_red)
            
            total_pixels = green_pixels + red_pixels
            if total_pixels > 0:
                # Определяем результат по преобладающему цвету
                result = green_pixels > red_pixels
                
                logger.debug(f"Анализ силы: зеленый={green_pixels}, красный={red_pixels}, "
                           f"результат={result}")
                
                return result
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при определении индикатора силы: {e}")
            return False

    # Основная функция для определения состояния кнопки 'Автоскилл'
    def find_auto_skill_button(self, image: np.ndarray) -> bool:
        """Определение состояния кнопки 'Автоскилл'"""
        logger.info("Определение состояния кнопки 'Автоскилл'")
        try:
            # Конвертируем в grayscale если изображение цветное
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
                
            # Масштабируем шаблоны если необходимо
            true_template, false_template = self.scale_template_if_needed(
                gray,
                self.true_auto_skill_template,
                self.false_auto_skill_template
            )
            
            # Проверяем совпадение с шаблонами
            true_result = cv2.matchTemplate(gray, true_template, cv2.TM_CCOEFF_NORMED)
            false_result = cv2.matchTemplate(gray, false_template, cv2.TM_CCOEFF_NORMED)
            
            true_val = np.max(true_result)
            false_val = np.max(false_result)
            
            logger.debug(f"Совпадение автоскилла: true={true_val:.3f}, false={false_val:.3f}")
            
            # Если false_val больше, значит кнопка неактивна (false)
            is_enabled = false_val >= true_val
            
            # Дополнительная проверка свечения для неактивной кнопки
            if is_enabled:
                _, bright_mask = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
                bright_pixels = cv2.countNonZero(bright_mask)
                has_glow = bright_pixels > (gray.size * 0.1)
                logger.debug(f"Проверка свечения: has_glow={has_glow}, bright_pixels={bright_pixels}")
                is_enabled = has_glow
            
            logger.info(f"Состояние кнопки 'Автоскилл': {is_enabled}")
            return is_enabled
                
        except Exception as e:
            logger.error(f"Ошибка при определении состояния автоскилла: {e}")
            return False

    # Основная функция для определения состояния наград в Daily Task
    def find_daily_task_rewards(self, image: np.ndarray) -> bool:
        """Определение состояния наград в Daily Task"""
        try:
            # Конвертируем в grayscale если изображение цветное
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
                
            # Масштабируем шаблоны если необходимо
            true_template, false_template = self.scale_template_if_needed(
                gray,
                self.true_daily_task_rewards_template,
                self.false_daily_task_rewards_template
            )
            
            # Проверяем совпадение с шаблонами
            true_result = cv2.matchTemplate(gray, true_template, cv2.TM_CCOEFF_NORMED)
            false_result = cv2.matchTemplate(gray, false_template, cv2.TM_CCOEFF_NORMED)
            
            true_val = np.max(true_result)
            false_val = np.max(false_result)
            
            logger.debug(f"Совпадение наград: true={true_val:.3f}, false={false_val:.3f}")
            
            # Определяем состояние по лучшему совпадению
            result = true_val > false_val
            
            # Дополнительная проверка через HSV для определения красного индикатора
            # Не знаю насколько эффективная реализация 
            # Как показывает практика, чем выше область изображения, тем эффективнее результат сравнения объекта
            '''
            if result:
                hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
                
                # Определяем диапазоны для красного цвета
                lower_red1 = np.array([0, 100, 100])
                upper_red1 = np.array([10, 255, 255])
                lower_red2 = np.array([160, 100, 100])
                upper_red2 = np.array([180, 255, 255])
                
                # Создаем маски для красного цвета
                mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
                mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
                mask_red = cv2.bitwise_or(mask_red1, mask_red2)
                
                # Подсчитываем красные пиксели
                red_pixels = cv2.countNonZero(mask_red)
                total_pixels = image.shape[0] * image.shape[1]
                
                # Если красных пикселей больше 5% от общего количества
                has_red_indicator = red_pixels > (total_pixels * 0.05)
                logger.debug(f"Проверка красного индикатора: has_red_indicator={has_red_indicator}")
                result = result and has_red_indicator
                
            logger.debug(f"Результат проверки наград: {result} (красный индикатор: {has_red_indicator}) (true_val: {true_val}, false_val: {false_val})")
            return result
            '''
                
        except Exception as e:
            logger.error(f"Ошибка при определении состояния наград: {e}")
            return False