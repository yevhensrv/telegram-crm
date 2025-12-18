# Файл: bot/main.py

import asyncio
import logging
import os
from fastapi import FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from aiogram.exceptions import TelegramBadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler # Для напоминаний
import uvicorn

# Импорт конфигурации и обработчиков
from bot.config import TOKEN, WEBAPP_URL, APP_BASE_URL 
from bot.database import init_database
from bot.handlers import start, workspaces, tasks, reminders
from bot.api import app as api_app # ИМПОРТИРУЕМ ГЛАВНОЕ ПРИЛОЖЕНИЕ API/WEBAPP

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ----------------- FastAPI/WEBHOOK ENDPOINT -----------------

@api_app.post(f"/webhook/{TOKEN}") 
async def telegram_webhook(request: Request):
    """Принимаем обновления от Telegram и передаем их диспетчеру aiogram"""
    try:
        json_data = await request.json()
        update = Update(**json_data)
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as e:
        logging.error(f"Unhandled error in webhook: {e}")
        return {"ok": False, "error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR

# ----------------- АПС Планировщик для напоминаний (Нужна функция) -----------------

async def check_reminders_job(bot: Bot):
    """Задача планировщика для проверки напоминаний."""
    # (Здесь нужна функция, чтобы этот код работал. Я предполагаю, что она у тебя есть, 
    # если нет, убедись, что она импортирована или скопирована)
    
    # ПРЕДПОЛАГАЕМ, что db.get_pending_reminders() работает
    from bot import database as db 
    pending_reminders = await db.get_pending_reminders()
    # ... (логика отправки напоминаний)


# ----------------- STARTUP LOGIC -----------------

async def on_startup_logic(bot: Bot):
    await init_database()
    
    # 1. Устанавливаем вебхук
    webhook_url = f"{APP_BASE_URL}webhook/{TOKEN}"
    await bot.set_webhook(webhook_url)
    
    logging.info(f"✅ Webhook установлен на: {webhook_url}")
    print("🚀 Бот запущен и готов принимать вебхуки!")

# 2. Регистрация роутеров бота
dp.include_router(start.router)
dp.include_router(workspaces.router)
dp.include_router(tasks.router)
dp.include_router(reminders.router)


@api_app.on_event("startup")
async def on_startup_event():
    # Настраиваем планировщик
    scheduler = AsyncIOScheduler()
    # Предполагаем, что функция check_reminders_job есть в основном файле или импортирована
    # Если ты используешь `reminders.py`, нужно импортировать его job
    
    # Если ты использовал код, который я прислал ранее:
    await on_startup_logic(bot)
    
    # Важно: если check_reminders_job определена в другом месте, замени эту строку:
    # scheduler.add_job(check_reminders_job, 'interval', seconds=30, args=[bot])
    # scheduler.start()

if __name__ == "__main__":
    # Команда для запуска, которую должен выполнять Render (через Procfile)
    uvicorn.run(api_app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
