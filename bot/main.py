# Файл: bot/main.py

import asyncio
import logging
import os
from fastapi import Request
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uvicorn
from aiogram.enums import ParseMode

# Импорт конфигурации
from bot.config import TOKEN, WEBAPP_URL, APP_BASE_URL

# Импорт базы данных
from bot.database import init_database

# Импорт API приложения и роутера
from bot.api import api_app, router as api_router

# Импорт роутеров бота
from bot.handlers import routers

# Настройка логов
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Подключаем API роутер к FastAPI приложению
api_app.include_router(api_router)

# Регистрируем все роутеры бота
for router in routers:
    dp.include_router(router)


# ==================== ПЛАНИРОВЩИК НАПОМИНАНИЙ ====================

async def check_reminders_job(bot_instance: Bot):
    """Проверка и отправка напоминаний"""
    from bot import database as db
    
    try:
        pending_reminders = await db.get_pending_reminders()
        
        for reminder in pending_reminders:
            try:
                text = f"🔔 **Напоминание о задаче:**\n\n📋 {reminder['task_title']}"
                await bot_instance.send_message(
                    chat_id=reminder['telegram_id'],
                    text=text,
                    parse_mode=ParseMode.MARKDOWN
                )
                await db.mark_reminder_sent(reminder['id'])
                logger.info(f"Напоминание {reminder['id']} отправлено")
            except Exception as e:
                logger.error(f"Ошибка отправки напоминания {reminder['id']}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка в check_reminders_job: {e}")


# ==================== WEBHOOK ENDPOINT ====================

# Используем фиксированный путь вместо токена
WEBHOOK_PATH = "/webhook"

@api_app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """Обработка входящих обновлений от Telegram"""
    try:
        json_data = await request.json()
        update = Update(**json_data)
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Ошибка в webhook: {e}")
        return {"ok": False, "error": str(e)}


# ==================== СОБЫТИЯ ЗАПУСКА/ОСТАНОВКИ ====================

@api_app.on_event("startup")
async def on_startup():
    """Действия при запуске приложения"""
    
    # Инициализируем базу данных
    await init_database()
    logger.info("✅ База данных инициализирована")
    
    # Устанавливаем вебхук
    if APP_BASE_URL:
        # Убираем trailing slash если есть
        base_url = APP_BASE_URL.rstrip('/')
        webhook_url = f"{base_url}{WEBHOOK_PATH}"
        
        try:
            # Сначала удаляем старый webhook
            await bot.delete_webhook(drop_pending_updates=True)
            # Устанавливаем новый
            await bot.set_webhook(webhook_url)
            logger.info(f"✅ Webhook установлен: {webhook_url}")
        except Exception as e:
            logger.error(f"❌ Ошибка установки webhook: {e}")
    else:
        logger.warning("⚠️ APP_BASE_URL не установлен, webhook не настроен")
    
    # Запускаем планировщик напоминаний
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_reminders_job, 
        'interval', 
        seconds=30, 
        args=[bot],
        id='reminders_job',
        replace_existing=True
    )
    scheduler.start()
    logger.info("✅ Планировщик напоминаний запущен")
    
    print("🚀 Бот успешно запущен!")


@api_app.on_event("shutdown")
async def on_shutdown():
    """Действия при остановке приложения"""
    try:
        await bot.session.close()
        logger.info("👋 Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка при остановке: {e}")


# ==================== HEALTH CHECK ====================

@api_app.get("/health")
async def health_check():
    """Проверка работоспособности"""
    return {"status": "ok", "bot": "running"}


# ==================== ТОЧКА ВХОДА ====================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    print(f"🔧 Запуск на порту {port}...")
    
    uvicorn.run(
        api_app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

