# tracer.py

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from loguru import logger
from playwright.async_api import Page
import json

class TracerManager:
    def __init__(self, page: Page, device_config: Dict[str, Any]):
        self.page = page
        self.device_config = device_config
        self.trace_dir = Path("./recordings/tracer")
        self.current_trace_dir = None
        self.is_tracing = False
        self.visual_interactions = []
        self._setup_directories()
        logger.info("Инициализирован TracerManager")

    def _setup_directories(self):
        """Создание необходимых директорий"""
        try:
            self.trace_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_trace_dir = self.trace_dir / f"trace_{timestamp}"
            self.current_trace_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Создана директория для трейсов: {self.current_trace_dir}")
        except Exception as e:
            logger.error(f"Ошибка создания директорий трейсера: {e}")
            raise

    async def start_tracing(self):
        """Запуск трейсинга"""
        try:
            self.is_tracing = True
            logger.info("Начало трейсинга...")
            await self._inject_advanced_tracker()
            logger.info("Трейсинг успешно запущен")
        except Exception as e:
            logger.error(f"Ошибка запуска трейсинга: {e}")
            self.is_tracing = False
            raise

    async def _inject_advanced_tracker(self):
        """Инжектирование продвинутого трекера для Telegram Mini Apps"""
        try:
            script = """
            window.telegramTracker = {
                events: [],
                interactions: [],
                _state: {
                    lastViewportHeight: 0,
                    lastState: null,
                    interactionPoints: []
                },

                // Основная функция логирования
                logEvent: function(event) {
                    const tg = window.Telegram?.WebApp;
                    if (!tg) return;

                    const baseState = {
                        viewportHeight: tg.viewportHeight,
                        viewportStableHeight: tg.viewportStableHeight,
                        viewportWidth: window.innerWidth || document.documentElement.clientWidth
                    };

                    const enrichedEvent = {
                        ...event,
                        timestamp: Date.now(),
                        coordinates: event.coordinates || this._state.interactionPoints[this._state.interactionPoints.length - 1],
                        webAppState: baseState
                    };

                    this._saveEvent(enrichedEvent);
                },

                // Проверка изменения состояния
                _hasStateChanged: function() {
                    const tg = window.Telegram?.WebApp;
                    if (!tg) return false;

                    const currentState = {
                        height: tg.viewportHeight,
                        expanded: tg.isExpanded
                    };

                    const changed = JSON.stringify(currentState) !== JSON.stringify(this._state.lastState);
                    this._state.lastState = currentState;
                    return changed;
                },

                // Сохранение события
                _saveEvent: function(event) {
                    this.events.push(event);
                    console.log('TELEGRAM_TRACKER_EVENT:', JSON.stringify(event));
                },

                // Отслеживание событий DOM
                _trackDOMEvents: function() {
                    const trackableEvents = ['click', 'touchstart', 'touchend'];
                    
                    trackableEvents.forEach(eventName => {
                        document.addEventListener(eventName, (e) => {
                            // Пропускаем все события связанные с canvas
                            if (e.target.tagName === 'CANVAS') {
                                return;
                            }

                            const coordinates = {
                                x: e instanceof MouseEvent ? e.clientX : e.touches[0].clientX,
                                y: e instanceof MouseEvent ? e.clientY : e.touches[0].clientY
                            };

                            this._state.interactionPoints.push(coordinates);
                            if (this._state.interactionPoints.length > 10) {
                                this._state.interactionPoints.shift();
                            }

                            // Получаем текст элемента
                            let elementText = '';
                            if (e.target.tagName === 'DIV') {
                                elementText = e.target.textContent?.trim() || '';
                            }

                            const eventData = {
                                type: 'dom_event',
                                event: eventName,
                                target: {
                                    tagName: e.target.tagName,
                                    className: e.target.className,
                                    id: e.target.id,
                                    text: elementText
                                },
                                coordinates: coordinates
                            };

                            this.logEvent(eventData);
                        }, true);
                    });
                },

                // Отслеживание событий WebApp
                _trackWebAppEvents: function() {
                    const tg = window.Telegram?.WebApp;
                    if (!tg) return;

                    const events = [
                        'viewportChanged'
                    ];
                    
                    events.forEach(event => {
                        tg.onEvent(event, (data) => {
                            const eventData = {
                                type: 'webapp_event',
                                name: event,
                                data: data
                            };

                            if (event === 'viewportChanged') {
                                eventData.viewport = {
                                    height: tg.viewportHeight,
                                    stableHeight: tg.viewportStableHeight,
                                    previousHeight: this._state.lastViewportHeight
                                };
                                this._state.lastViewportHeight = tg.viewportHeight;
                            }

                            this.logEvent(eventData);
                        });
                    });
                },

                // Инициализация
                init: function() {
                    this._trackWebAppEvents();
                    this._trackDOMEvents();
                    
                    this.logEvent({
                        type: 'tracker_initialized',
                        timestamp: Date.now()
                    });
                }
            };

            // Запуск после инициализации WebApp
            const initTracker = () => {
                if (window.Telegram?.WebApp) {
                    window.telegramTracker.init();
                } else {
                    setTimeout(initTracker, 100);
                }
            };
            
            initTracker();
            """;

            # Инжектируем скрипт
            await self.page.add_init_script(script)
            
            # Добавляем слушатель консоли
            self.page.on("console", self._handle_tracker_event)
            
            logger.info("Продвинутый трекер для Telegram Mini Apps успешно инжектирован")
        
        except Exception as e:
            logger.error(f"Ошибка инжектирования трекера: {e}")
            raise

    async def _handle_tracker_event(self, msg):
        """Обработка событий трекера из консоли"""
        try:
            if msg.text.startswith('TELEGRAM_TRACKER_EVENT:'):
                event_data = json.loads(msg.text.replace('TELEGRAM_TRACKER_EVENT:', ''))
                await self._handle_interaction(event_data)
        except Exception as e:
            logger.error(f"Ошибка обработки события трекера: {e}")

    async def _handle_interaction(self, interaction: Dict):
        """Обработка взаимодействий"""
        try:
            self.visual_interactions.append(interaction)
            
            # Сохраняем в файл
            interactions_file = self.current_trace_dir / 'interactions.json'
            
            existing_data = []
            if interactions_file.exists():
                with open(interactions_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    
            existing_data.append(interaction)
            
            with open(interactions_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
                
            logger.debug(f"Записано взаимодействие: {interaction['type']} - {interaction.get('action')}")
            
        except Exception as e:
            logger.error(f"Ошибка обработки взаимодействия: {e}")

    async def stop_tracing(self):
        """Остановка трейсинга"""
        if not self.is_tracing:
            return
        try:
            self.is_tracing = False
            logger.info("Трейсинг успешно остановлен")
        except Exception as e:
            logger.error(f"Ошибка остановки трейсинга: {e}")
        finally:
            self.is_tracing = False