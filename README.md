
<div align="center">
  <img src="./templates/git/github_logo.webp" alt="Bombie Bot Logo" width="200"/>
  
  # 🤖 BOMBIE BOT
  ### НАША КОМАНДА [HIDDENCODE](https://t.me/hidden_coding)
  
  [![Static Badge](https://img.shields.io/badge/Telegram-Channel-Link?style=for-the-badge&logo=Telegram&logoColor=white&logoSize=auto&color=blue)](https://t.me/hidden_coding)
  [![Static Badge](https://img.shields.io/badge/Telegram-Chat-yes?style=for-the-badge&logo=Telegram&logoColor=white&logoSize=auto&color=blue)](https://t.me/hidden_codding_chat)
  [![Static Badge](https://img.shields.io/badge/Telegram-Bot%20Link-Link?style=for-the-badge&logo=Telegram&logoColor=white&logoSize=auto&color=blue)](https://t.me/catizenbot/bombie?startapp=g_1002_43630755)

## [HIDDEN CODE MARKET](https://t.me/hcmarket_bot?start=referral_355876562)

#### - [Paws wallet connector](https://t.me/hcmarket_bot?start=referral_355876562-project_1016)
#### - [Premium notpixel](https://t.me/hcmarket_bot?start=referral_355876562-project_1015)
#### - [Blum wallet connector](https://t.me/hcmarket_bot?start=referral_355876562-project_1002)
#### - [Telegram warning up](https://t.me/hcmarket_bot?start=referral_355876562-project_1001)
</div>

<div align="center">
  <br />
  <h2>🎉 ВАЖНОЕ ОБНОВЛЕНИЕ 🎉</h2>
  
  > ### 🚀 Релиз версии 1.2 
  > Бот готов к использованию! На данный момент доступен базовый функционал.  
  > Следите за обновлениями для получения полного функционала.
  
  [![Static Badge](https://img.shields.io/badge/📋_Исправления-ver_1.2-blue)](#-исправлено)

  <br />
</div>

## 📋 Содержание
- [Установка](#-установка)
- [Основная логика](#-основная-логика)
- [Реализованные функции](#-реализовано)
- [Обновления](#-обновления-и-версии)
- [Для контрибьюторов](#-для-контрибьюторов)
- [Недостатки](#-недостатки)
- [Будущие разработки](#-планы-и-будущие-разработки)
- [Контакты](#-контакты)

## 🛠 Установка

<details>
<summary>1. Устанавливаем cargo пакет для Rust</summary>

[![Rust Installation](https://img.shields.io/badge/Rust-Installation-orange)](https://www.rust-lang.org/tools/install)

```bash
# Linux/MacOS/Windows:
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```
</details>

<details>
<summary>2. Устанавливаем python 3.10</summary>

```bash
# MacOS:
brew install python@3.10

# Linux:
sudo apt install python3.10

# Windows:
# Скачать с https://www.python.org/downloads/release/python-31010/
```
</details>

<details>
<summary>3. Скачиваем проект</summary>

```bash
git clone https://github.com/Panda404NotFound/bombie_bot.git
```
</details>

<details>
<summary>4. Запуск проекта</summary>

```bash
# Режим отладки:
RUST_LOG=debug cargo run

# Режим выпуска:
cargo run --release
cd target/release
./bombie_bot
```
</details>

## 🔄 Основная логика

<div align="center">
  
  ```mermaid
  graph TD
    A[Вход в Telegram сессию] --> B[Поиск бота]
    B --> C[Запуск ссылки на бота]
    C --> D[Вход в бота]
    D --> E[Выполнение действий]
  ```
  
</div>

## ✨ Реализовано (ver. 1.0)

- 🎭 Эмуляция устройства и браузера с помощью playwright
- 🐍 Локальный venv внутри python_env куда устанавливаются все зависимости включая playwright
- 🔄 Контроль версий, зависимостей и установки через rust py_modules/
- 🌐 Взаимодействие с браузером через pyo3 и python код внутри src/python/bombie/*
- 📦 Открытие сундуков, выбор силы и автоматическая покупка/продажа
- 🎯 Проверка "auto" кнопки и автоматическое нажатие в случае отсутствия
- ⚡ Обработка Daily Task заданий, сбор наград
- ⏱️ Эмуляция задержки и рандома в нажатиях
- 💻 Мультиплатформенность за счет cargo пакетника

## 📝 Обновления и Версии

<details>
<summary>Версия 1.0 (25.11.24)</summary>

### 🚀 Изменения
- 📦 Процесс обработки сундуков (без auto кнопки, вручную с автовыбором силы)
- ⚛️ Атомарный контроль модулей, ожидание завершения и таймеры
- 🌐 Одна сессия телеграмм, работа с playwright
- 📍 Трейсер координат взаимодействия с Canvas API
- 📸 Контроль скриншотов и записей видео действий бота
- 📄 Два лог файла для отслеживаания работы бота
- 🔄 Прямое взаимодействие на уровне клиента и сервера
</details>

## 💻 Для Контрибьюторов

<details>
<summary>Структура проекта</summary>

### Входная точка
```python
# Инициализация и запуск логики WebApp
logger.info("Запуск основной логики действий бота")
webapp_logic = WebAppLogic(self.page)
logic_task = asyncio.create_task(webapp_logic.start_logic())
```

### 📁 Основные модули (src/python/bombie/*)
- `task_action.py` и `chest_action.py` - автоматизация действий бота
- `cordination_module.py` - координация и Canvas API
- `module_manager.py` - управление модулями
- `ocr_manager.py` и `cv_manager.py` - работа с нейросетями
- `templates/*` - шаблоны для нейросети
</details>

## ⚠️ Недостатки

- 🔧 Нет гибкого модульного взаимодействия с разными клиентами
- 🌐 Нет поддержки proxy
- 📝 Нет авторегистрации
- 🔨 "Молдованская" реализация входа в telethon клиента

## 🔮 Планы и Будущие Разработки

<table>
<tr>
<td>🔄 Автообновления через GitHub releases</td>
<td>🤖 Телеграм бот для контроля сессий</td>
</tr>
<tr>
<td>🎮 Полная реализация bombie автоматизаций</td>
<td>🎭 Полная эмуляция человеческого поведения</td>
</tr>
<tr>
<td>👥 Работа с несколькими сессиями</td>
<td>⚡ Многопоточность и паралелизация</td>
</tr>
<tr>
<td>🐳 Автоскрипты и контейнеризация</td>
<td>📈 CI/CD и масштабирование</td>
</tr>
</table>

## 🛠 Исправлено
> 🔧 Тут будут исправления и доработки
Исправления на 25.11.24:

ver. 1.2:
- Добавления обработка цветных изображений 
- Улучшено распознавание изменений для логики
- Улучшена логика взаимодействия с объектами

Исправления на 25.11.24:

ver. 1.1:

- 2FA авторизация с повторными попытками
- Проблемы с загрузкой OCR модели и SSL разрешениями
- Запуск Daily Task в первую очередь, потом сундуки
- Логические ошибки при проверке меню заданий
- Добавлена выбор записи логов и трейсинга
- Проверка не корректного определения силы сундука
- Удаление логов при первом запуске

## 📞 Контакты

<div align="center">
  
[![Связь с Разработчиком](https://img.shields.io/badge/Разработчик-Telegram-blue?style=for-the-badge&logo=telegram)](https://t.me/brahman_brahman)
[![Сообщество Сигм](https://img.shields.io/badge/Комьюнити_Сигм-Telegram-blue?style=for-the-badge&logo=telegram)](https://t.me/hidden_coding)

</div>
