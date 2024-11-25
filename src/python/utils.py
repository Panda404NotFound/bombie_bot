import asyncio
import random
from datetime import datetime
import os
from pathlib import Path
from typing import Optional
import ffmpeg
from loguru import logger

class HumanBehavior:
    """Класс для имитации человеческого поведения"""
    
    @staticmethod
    async def random_delay():
        """Генерирует случайную задержку от 0.450 до 1.050 секунд с возможностью десятичных значений"""
        delay = round(random.uniform(0.450, 1.050), 3)
        await asyncio.sleep(delay)
        return delay
    
    @staticmethod
    async def random_scroll():
        """Генерирует случайный скролл"""
        return random.randint(100, 500)

class ScreenRecorder:
    """Класс для управления записью экрана и скриншотами"""
    def __init__(self, output_dir: str = "./recordings", enable_video: bool = False, enable_screenshots: bool = True):
        self.output_dir = Path(output_dir)
        self.screenshots_dir = self.output_dir / "screenshots"
        self.videos_dir = self.output_dir / "videos"
        
        # Флаги управления записью
        self.enable_video = enable_video
        self.enable_screenshots = enable_screenshots
        
        # Создаем директории если включена соответствующая функция
        if self.enable_screenshots:
            self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        if self.enable_video:
            self.videos_dir.mkdir(parents=True, exist_ok=True)
            
    def get_screenshot_path(self, action_name: str) -> str:
        """Генерирует путь для скриншота"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return str(self.screenshots_dir / f"{action_name}_{timestamp}.png")
    
    def get_video_path(self) -> str:
        """Генерирует путь для видео"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return str(self.videos_dir / f"session_{timestamp}.mp4")
    
    async def take_screenshot(self, page, action_name: str):
        """Делает скриншот текущего состояния страницы"""
        if not self.enable_screenshots:
            return
            
        try:
            screenshot_path = self.get_screenshot_path(action_name)
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Сделан скриншот действия '{action_name}': {screenshot_path}")
        except Exception as e:
            logger.error(f"Ошибка при создании скриншота: {e}")