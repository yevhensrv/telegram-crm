"""
Конфигурация бота
Здесь хранятся все настройки
"""

import os
from dotenv import load_dotenv

# Загружаем переменные из файла .env
load_dotenv()

# Токен бота (берём из .env файла)
BOT_TOKEN = os.getenv("BOT_TOKEN")

# URL веб-приложения (пока оставим пустым)
WEBAPP_URL = os.getenv("WEBAPP_URL", "")

# Проверка что токен есть
if not BOT_TOKEN:
    raise ValueError("❌ Не найден BOT_TOKEN в файле .env!")