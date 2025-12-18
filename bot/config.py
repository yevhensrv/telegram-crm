# Файл: bot/config.py
"""
Конфигурация бота
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота
TOKEN = os.getenv("BOT_TOKEN")

# Основной URL сервиса Render
APP_BASE_URL = os.getenv("APP_BASE_URL")

# URL веб-приложения (Mini App)
WEBAPP_URL = os.getenv("WEBAPP_URL") or APP_BASE_URL

# Проверка токена
if not TOKEN:
    raise ValueError("❌ Не найден BOT_TOKEN!")
