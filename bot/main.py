"""
Запуск бота и API вместе
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uvicorn
from starlette.requests import Request # Добавляем импорт для FastAPI

from bot.config import BOT_TOKEN
from bot import database as db
from bot.api import app as api_app # FastAPI приложение
from bot.handlers.routers import main_router # Импортируем роутеры

# Устанавливаем базовое логирование
logging.basicConfig(level=logging.INFO)

# =======================
# ФУНКЦИИ БОТА / ПЛАНИРОВЩИК
# =======================

async def check_reminders_job(bot: Bot):
    """Задача планировщика для проверки напоминаний."""
    # Обработка напоминаний
    # Этот код уже работает, судя по логам
    pending_reminders = await db.get_pending_reminders()
    for reminder in pending_reminders:
        text = f"🔔 **Напоминание о задаче:** {reminder['task_title']}"
        await bot.send_message(
            chat_id=reminder['telegram_id'],
            text=text,
            parse_mode=ParseMode.MARKDOWN
        )
        await db.mark_reminder_sent(reminder['id'])


async def start_bot():
    """Главная функция запуска бота и вебхука."""
    
    # 1. Инициализация базы данных
    await db.init_database() 

    # 2. Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # 3. Регистрация всех роутеров
    dp.include_router(main_router)
    
    # 4. Настройка планировщика (для напоминаний)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders_job, 'interval', seconds=30, args=[bot])
    scheduler.start()
    
    # 5. Настройка Webhook
    
    # URL твоего Render-сервиса
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL") 
    
    if not WEBHOOK_URL:
        # Если переменная окружения WEBHOOK_URL не установлена, 
        # возможно, Render не знает, куда отправлять запросы.
        logging.error("WEBHOOK_URL environment variable is not set!")
        # В этом случае, если ты уверен, что запускаешься через Uvicorn, продолжаем, 
        # но убедись, что ты правильно настроил Webhook в настройках Render.
        
    
    # Регистрация Webhook для FastAPI
    # Создаем конечную точку для приема обновлений Telegram
    @api_app.post(f"/webhook/{BOT_TOKEN}")
    async def telegram_webhook(request: Request):
        json_data = await request.json()
        await dp.feed_raw_update(bot, json_data)
        return {"ok": True}
        
    # Установка вебхука при старте
    async def set_webhook():
        await bot.delete_webhook() # Удаляем старый, если есть
        await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook/{BOT_TOKEN}")
        logging.info(f"✅ Webhook set to: {WEBHOOK_URL}/webhook/{BOT_TOKEN}")

    dp.startup.register(set_webhook)

    # 6. Запуск Uvicorn (запускает FastAPI и Dispatcher)
    
    config = uvicorn.Config(
        api_app, 
        host="0.0.0.0", 
        port=int(os.environ.get("PORT", 8080)),
        log_level="info"
    )
    server = uvicorn.Server(config)
    
    # Запускаем сервер
    await server.serve()


if __name__ == '__main__':
    try:
        asyncio.run(start_bot())
    except Exception as e:
        logging.critical(f"Global error during startup: {e}")
