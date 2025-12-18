"""
Конфигурация бота
Здесь хранятся все настройки
"""

import os
from dotenv import load_dotenv

# Загружаем переменные из файла .env (если работаем локально)
load_dotenv()

# Токен бота
TOKEN = os.getenv("BOT_TOKEN") 

# Основной URL сервиса Render, который будет использоваться для Webhook
APP_BASE_URL = os.getenv("APP_BASE_URL")

# URL веб-приложения (Mini App), обычно совпадает с APP_BASE_URL
WEBAPP_URL = os.getenv("WEBAPP_URL") or APP_BASE_URL # Используем APP_BASE_URL, если WEBAPP_URL не задан

# Проверка, что токен есть
if not TOKEN:
    raise ValueError("❌ Не найден BOT_TOKEN!")

# Проверка, что установлен APP_BASE_URL для Webhook на Render
if not APP_BASE_URL and os.getenv("RENDER"):
    raise ValueError("❌ Переменная APP_BASE_URL должна быть установлена для работы на Render!")
