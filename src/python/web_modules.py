import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger
from playwright.async_api import Page
import json

class CanvasInteractionTracker:
    """Класс для отслеживания взаимодействий с canvas"""
    def __init__(self, page: Page):
        self.page = page
        self.trace_dir = Path("./recordings/tracer/canvas")
        self.current_session = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.setup_trace_directory()
        
    def setup_trace_directory(self):
        """Создание директории для логов"""
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        
    async def start_tracking(self):
        """Запуск отслеживания взаимодействий"""
        await self.page.evaluate("""
            () => {
                window.canvasTracker = {
                    interactions: [],
                    
                    logInteraction: function(event) {
                        const interaction = {
                            type: event.type,
                            coordinates: {
                                x: event.clientX,
                                y: event.clientY
                            },
                            timestamp: Date.now(),
                            target: {
                                id: event.target.id,
                                type: event.target.tagName.toLowerCase()
                            }
                        };
                        
                        this.interactions.push(interaction);
                        console.log('CANVAS_INTERACTION:', JSON.stringify(interaction));
                    },
                    
                    init: function() {
                        const canvas = document.querySelector('#GameCanvas');
                        if (!canvas) return;
                        
                        ['click'].forEach(eventType => {
                            canvas.addEventListener(eventType, this.logInteraction.bind(this));
                        });
                    }
                };
                
                window.canvasTracker.init();
            }
        """)
        
        # Добавляем обработчик консоли для логирования
        self.page.on("console", self._handle_interaction_event)
        
    async def _handle_interaction_event(self, msg):
        """Обработка событий взаимодействия"""
        try:
            if msg.text.startswith('CANVAS_INTERACTION:'):
                interaction_data = json.loads(msg.text.replace('CANVAS_INTERACTION:', ''))
                await self._save_interaction(interaction_data)
        except Exception as e:
            logger.error(f"Ошибка обработки события взаимодействия: {e}")
            
    async def _save_interaction(self, interaction: Dict):
        """Сохранение взаимодействия в файл"""
        try:
            file_path = self.trace_dir / f"canvas_interactions_{self.current_session}.json"
            
            existing_data = []
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    
            existing_data.append(interaction)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
                
            logger.debug(f"Записано взаимодействие с canvas: {interaction['type']}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения взаимодействия: {e}")

class GameCanvasHandler:
    """Основной класс для работы с игровым canvas"""
    def __init__(self, page: Page):
        self.page = page
        self.tracker = CanvasInteractionTracker(page)

    async def initialize(self) -> bool:
        try:
            # Ждем загрузки страницы
            await self.page.wait_for_load_state('networkidle')
            logger.info("Страница для web_modules успешно загружена")
                
            await self.tracker.start_tracking()
            logger.info("Canvas успешно инициализирован и готов к работе")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации canvas: {e}")
            return False