# Файл: bot/main.py

import asyncio
import logging
import os
from fastapi import Request, status
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uvicorn
from aiogram.enums import ParseMode

# Импорт конфигурации и обработчиков
from bot.config import TOKEN, WEBAPP_URL, APP_BASE_URL 
from bot.database import init_database
from bot.handlers import start, workspaces, tasks, reminders, comments
from bot.api import api_app, router as api_router

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Подключаем API роутер к приложению
api_app.include_router(api_router)


# ----------------- АПС Планировщик для напоминаний -----------------

async def check_reminders_job(bot_instance: Bot):
    from bot import database as db 
    
    try:
        pending_reminders = await db.get_pending_reminders()
        for reminder in pending_reminders:
            text = f"🔔 **Напоминание о задаче:** {reminder['task_title']}"
            try:
                await bot_instance.send_message(
                    chat_id=reminder['telegram_id'],
                    text=text,
                    parse_mode=ParseMode.MARKDOWN
                )
                await db.mark_reminder_sent(reminder['id'])
            except Exception as e:
                logging.error(f"Failed to send reminder {reminder['id']}: {e}")
    except Exception as e:
        logging.error(f"Error in check_reminders_job: {e}")


# ----------------- FastAPI/WEBHOOK ENDPOINT -----------------

@api_app.post(f"/{TOKEN}")
async def telegram_webhook(request: Request):
    try:
        json_data = await request.json()
        update = Update(**json_data)
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as e:
        logging.error(f"Unhandled error in webhook: {e}")
        return {"ok": False, "error": str(e)}


# ----------------- STARTUP LOGIC -----------------

@api_app.on_event("startup")
async def on_startup_event():
    await init_database()
    
    # Проверяем наличие URL для вебхука
    if not APP_BASE_URL:
        logging.error("APP_BASE_URL environment variable is not set!")
        print("⚠️ Бот запущен БЕЗ вебхука (APP_BASE_URL не установлен)")
    else:
        # Устанавливаем вебхук
        webhook_url = f"{APP_BASE_URL}/{TOKEN}"
        try:
            await bot.set_webhook(webhook_url)
            logging.info(f"✅ Webhook установлен на: {webhook_url}")
        except Exception as e:
            logging.error(f"Failed to set webhook: {e}")
    
    # Настраиваем планировщик
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders_job, 'interval', seconds=30, args=[bot])
    scheduler.start()
    
    print("🚀 Бот запущен и готов принимать вебхуки!")


# ----------------- MAIN EXECUTION -----------------

# Регистрация роутеров бота
dp.include_router(start.router)
dp.include_router(workspaces.router)
dp.include_router(tasks.router)
dp.include_router(reminders.router)
dp.include_router(comments.router)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(api_app, host="0.0.0.0", port=port)
