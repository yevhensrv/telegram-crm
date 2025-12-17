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

from bot.config import BOT_TOKEN
from bot import database as db
from bot.handlers import routers
from bot.api import app as api_app

# Логи
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Бот
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()

# Планировщик напоминаний
scheduler = AsyncIOScheduler()


async def check_reminders():
    """Отправка напоминаний"""
    try:
        reminders = await db.get_pending_reminders()
        for r in reminders:
            try:
                await bot.send_message(r["telegram_id"], f"🔔 **Напоминание!**\n\n📋 {r['task_title']}")
                await db.mark_reminder_sent(r["id"])
            except:
                pass
    except:
        pass


async def run_bot():
    """Запуск бота"""
    for router in routers:
        dp.include_router(router)
    
    scheduler.add_job(check_reminders, 'interval', seconds=30)
    scheduler.start()
    
    logger.info("🤖 Бот запущен!")
    await dp.start_polling(bot)


async def run_api():
    """Запуск API"""
    port = int(os.environ.get("PORT", 8000))
    config = uvicorn.Config(api_app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    logger.info(f"🌐 Mini App: порт {port}")
    await server.serve()


async def main():
    """Главная функция"""
    await db.init_database()
    
    logger.info("=" * 40)
    logger.info("🚀 CRM СИСТЕМА ЗАПУСКАЕТСЯ...")
    logger.info("=" * 40)
    
    await asyncio.gather(run_bot(), run_api())


if __name__ == "__main__":
    asyncio.run(main())