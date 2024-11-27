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
                'false_task_action': None,
                'incorrect_equip_choice': None,
                'true_task_button_dayli_task': None
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
            self.true_autosell_template = cv2.imread(str(template_paths['true_autosell_set']))
            self.false_autosell_template = cv2.imread(str(template_paths['false_autosell_set']))
            self.true_power_template = cv2.imread(str(template_paths['true_power_chest']))
            self.false_power_template = cv2.imread(str(template_paths['false_power_chest']))
            self.false_auto_skill_template = cv2.imread(str(template_paths['false_auto_skill_button']))
            self.true_auto_skill_template = cv2.imread(str(template_paths['true_auto_skill_button']))
            self.true_daily_task_rewards_template = cv2.imread(str(template_paths['true_task_action']))
            self.false_daily_task_rewards_template = cv2.imread(str(template_paths['false_task_action']))
            self.incorrect_equip_choice_template = cv2.imread(str(template_paths['incorrect_equip_choice']))
            self.true_task_button_dayli_task_template = cv2.imread(str(template_paths['true_task_button_dayli_task']))


            # Проверка загруженных шаблонов
            templates = {
                'true_autosell_set': self.true_autosell_template,
                'false_autosell_set': self.false_autosell_template,
                'true_power_chest': self.true_power_template,
                'false_power_chest': self.false_power_template,
                'false_auto_skill_button': self.false_auto_skill_template,
                'true_auto_skill_button': self.true_auto_skill_template,
                'true_task_action': self.true_daily_task_rewards_template,
                'false_task_action': self.false_daily_task_rewards_template,
                'incorrect_equip_choice': self.incorrect_equip_choice_template,
                'true_task_button_dayli_task':self.true_task_button_dayli_task_template
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

        img_h, img_w = image.shape[:2]
        templ_h, templ_w = template1.shape[:2]
        
        if img_h < templ_h or img_w < templ_w:
            logger.debug(f"Масштабирование шаблона: img_h={img_h}, img_w={img_w}, templ_h={templ_h}, templ_w={templ_w}")
            scale = min(img_h / templ_h, img_w / templ_w) * scale_factor
            new_h = int(templ_h * scale)
            new_w = int(templ_w * scale)
            
            if new_h >= img_h or new_w >= img_w:
                logger.debug("Масштабированные размеры превышают размеры изображения. Возвращаем исходные шаблоны.")
                return template1, template2
                
            scaled_template1 = cv2.resize(template1, (new_w, new_h), interpolation=cv2.INTER_AREA)
            scaled_template2 = cv2.resize(template2, (new_w, new_h), interpolation=cv2.INTER_AREA)
            return scaled_template1, scaled_template2
        
        logger.debug(f"Шаблоны не масштабируются: img_h={img_h}, img_w={img_w}, templ_h={templ_h}, templ_w={templ_w}")
        return template1, template2

    # Основная функция для определения состояния чекбокса автопродажи
    def find_autosell_checkbox(self, image: np.ndarray) -> bool:
        """Определение состояния чекбокса автопродажи"""
            
        try:                
            # Проверяем совпадение с обоими шаблонами
            true_result = cv2.matchTemplate(image, self.true_autosell_template, cv2.TM_CCOEFF_NORMED)
            false_result = cv2.matchTemplate(image, self.false_autosell_template, cv2.TM_CCOEFF_NORMED)
            
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
            # Масштабируем шаблоны если необходимо
            true_template, false_template = self.scale_template_if_needed(
                image,
                self.true_auto_skill_template,
                self.false_auto_skill_template
            )
            
            # Проверяем совпадение с шаблонами
            true_result = cv2.matchTemplate(image, true_template, cv2.TM_CCOEFF_NORMED)
            false_result = cv2.matchTemplate(image, false_template, cv2.TM_CCOEFF_NORMED)
            
            true_val = np.max(true_result)
            false_val = np.max(false_result)
            
            logger.debug(f"Совпадение автоскилла: true={true_val:.3f}, false={false_val:.3f}")
            
            # Если false_val больше, значит кнопка неактивна (false)
            is_enabled = false_val >= true_val
            
            # Дополнительная проверка свечения для неактивной кнопки
            if is_enabled:
                # Конвертируем в grayscale для проверки яркости
                if len(image.shape) == 3:
                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                else:
                    gray = image
                    
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
            # Временное решение, возвращаем всегда True
            # Нужны доработки алгоритма определения наград

            # Масштабируем шаблоны если необходимо
            true_template, false_template = self.scale_template_if_needed(
                image,
                self.true_daily_task_rewards_template,
                self.false_daily_task_rewards_template
            )
            
            # Проверяем совпадение с шаблонами напрямую используя TM_CCOEFF_NORMED
            true_result = cv2.matchTemplate(image, true_template, cv2.TM_CCOEFF_NORMED)
            false_result = cv2.matchTemplate(image, false_template, cv2.TM_CCOEFF_NORMED)
            
            true_val = np.max(true_result)
            false_val = np.max(false_result)
            
            logger.debug(f"Совпадение наград: true={true_val:.3f}, false={false_val:.3f}")
            
            # Определяем состояние по лучшему совпадению
            result = true_val > false_val
            
            # Дополнительная проверка через HSV для определения красного индикатора
            # Не знаю насколько эффективная реализация 
            # Как показывает практика, чем выше область изображения, тем эффективнее результат сравнения объекта

            '''
            has_red_indicator = False 

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
            '''

            return result

        except Exception as e:
            logger.error(f"Ошибка при определении состояния наград: {e}")
            return False

    # Функция проверки не корректного выбора предмета для экипировки
    def find_incorrect_equip_choice(self, image: np.ndarray) -> bool:
        """
        Проверка некорректного выбора предмета для экипировки/продажи
        
        Args:
            image: Входное изображение для анализа
            
        Returns:
            bool: True если обнаружено предупреждение, False в противном случае
        """
        try:
            # Масштабируем шаблон если необходимо
            scaled_template = self.scale_template_if_needed(
                image,
                self.incorrect_equip_choice_template,
                self.incorrect_equip_choice_template
            )[0]  # Берем первый элемент, так как второй не нужен
            
            # Проверяем совпадение с шаблоном
            result = cv2.matchTemplate(image, scaled_template, cv2.TM_CCOEFF_NORMED)
            match_val = np.max(result)
            
            logger.debug(f"Совпадение предупреждения о некорректном выборе: {match_val:.3f}")
            
            # Возвращаем True если уверенность выше порога
            return match_val > 0.45
            
        except Exception as e:
            logger.error(f"Ошибка при проверке некорректного выбора предмета: {e}")
            return False