# Файл: bot/main.py

import asyncio
import logging
import os
from fastapi import Request, status
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from aiogram.exceptions import TelegramBadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uvicorn
from aiogram.enums import ParseMode

# Импорт конфигурации и обработчиков
from bot.config import TOKEN, WEBAPP_URL, APP_BASE_URL 
from bot.database import init_database
from bot.handlers import start, workspaces, tasks, reminders # Твои хэндлеры
from bot.api import app as api_app # ИМПОРТИРУЕМ ГЛАВНОЕ ПРИЛОЖЕНИЕ API/WEBAPP

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ----------------- АПС Планировщик для напоминаний -----------------

async def check_reminders_job(bot: Bot):
    from bot import database as db 
    
    pending_reminders = await db.get_pending_reminders()
    for reminder in pending_reminders:
        text = f"🔔 **Напоминание о задаче:** {reminder['task_title']}"
        await bot.send_message(
            chat_id=reminder['telegram_id'],
            text=text,
            parse_mode=ParseMode.MARKDOWN
        )
        await db.mark_reminder_sent(reminder['id'])


# ----------------- FastAPI/WEBHOOK ENDPOINT -----------------

@api_app.post(f"/{TOKEN}") # Эндпоинт для принятия вебхука
async def telegram_webhook(request: Request):
    try:
        json_data = await request.json()
        update = Update(**json_data)
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as e:
        logging.error(f"Unhandled error in webhook: {e}")
        return {"ok": False, "error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR

# ----------------- STARTUP LOGIC -----------------

@api_app.on_event("startup")
async def on_startup_event():
    await init_database()
    
    # 1. Устанавливаем вебхук
    webhook_url = f"{APP_BASE_URL}{TOKEN}"
    await bot.set_webhook(webhook_url)
    
    logging.info(f"✅ Webhook установлен на: {webhook_url}")
    print("🚀 Бот запущен и готов принимать вебхуки!")
    
    # 2. Настраиваем планировщик
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders_job, 'interval', seconds=30, args=[bot])
    scheduler.start()


# ----------------- MAIN EXECUTION -----------------

# 3. Регистрация роутеров бота
dp.include_router(start.router)
dp.include_router(workspaces.router)
dp.include_router(tasks.router)
dp.include_router(reminders.router)


if __name__ == "__main__":
    # Запускаем Uvicorn, который будет слушать порт и запускать api_app
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(api_app, host="0.0.0.0", port=port)
