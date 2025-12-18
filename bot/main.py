import asyncio
import logging
import os
from fastapi import FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from aiogram.exceptions import TelegramBadRequest

# Импорт конфигурации и обработчиков
from bot.config import TOKEN, WEBAPP_URL, APP_BASE_URL 
# Внимание: APP_BASE_URL - это основной URL вашего сервиса на Render! 
# Убедитесь, что он есть в bot/config.py!

from bot.database import init_database
from bot.handlers import start, workspaces, tasks, reminders
from bot import api

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
# Используем Webhook-режим для Render
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Инициализация FastAPI
app = FastAPI()

# ----------------- FastAPI HANDLERS -----------------

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "ok", "bot_running": True}

@app.post(f"/{TOKEN}") 
# Это наш URL-адрес вебхука. Например: https://telegram-crm-or80.onrender.com/8270912970:AAH...
async def telegram_webhook(request: Request):
    """Принимаем обновления от Telegram и передаем их диспетчеру aiogram"""
    try:
        json_data = await request.json()
        update = Update(**json_data)
        await dp.feed_update(bot, update)
        return {"ok": True}
    except TelegramBadRequest as e:
        # Это может случиться, если бот пытается отправить слишком длинное сообщение или похожая ошибка
        logging.error(f"TelegramBadRequest in webhook: {e}")
        return {"ok": False, "error": str(e)}, status.HTTP_400_BAD_REQUEST
    except Exception as e:
        logging.error(f"Unhandled error in webhook: {e}")
        return {"ok": False, "error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR

# Подключаем API маршруты
app.include_router(api.router, prefix="/api")

# Монтируем статические файлы WebApp
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
webapp_path = os.path.join(current_dir, "webapp")

if os.path.exists(webapp_path):
    app.mount("/", StaticFiles(directory=webapp_path, html=True), name="webapp")

# Регистрация роутеров бота
dp.include_router(start.router)
dp.include_router(workspaces.router)
dp.include_router(tasks.router)
dp.include_router(reminders.router)

# ----------------- STARTUP LOGIC -----------------

async def on_startup_logic(bot: Bot):
    await init_database()
    
    # 1. Устанавливаем вебхук на Render
    webhook_url = f"{APP_BASE_URL}{TOKEN}"
    await bot.set_webhook(webhook_url)
    
    logging.info(f"✅ Webhook установлен на: {webhook_url}")
    print("🚀 Бот запущен и готов принимать вебхуки!")

@app.on_event("startup")
async def on_startup_event():
    # Запускаем логику при старте FastAPI
    await on_startup_logic(bot)

if __name__ == "__main__":
    import uvicorn
    # В локальном режиме (если запустите не на Render) используем polling
    asyncio.run(dp.start_polling(bot))
    # Для продакшена на Render uvicorn запускается из Procfile
    # uvicorn.run(app, host="0.0.0.0", port=10000)
