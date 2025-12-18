"""
Команда /start и главное меню
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from bot import database as db
from bot.keyboards import get_main_menu
from bot.config import WEBAPP_URL

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start"""
    await state.clear()
    
    telegram_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    # Создаём пользователя
    user_id = await db.create_user(telegram_id, username, full_name)
    
    # Проверяем личное пространство
    workspaces = await db.get_user_workspaces(user_id)
    has_personal = any(ws.get("is_personal") for ws in workspaces)
    
    if not has_personal:
        await db.create_personal_workspace(user_id)
    
    welcome_text = f"""
👋 **Привет, {full_name}!**

Добро пожаловать в твою CRM-систему!

🏠 **Личное пространство** — твои личные задачи
👥 **Командные пространства** — работа с коллегами

**Что можно делать:**
• 📋 Создавать задачи
• 📊 Организовывать по воронкам
• 🔔 Ставить напоминания
• 👥 Работать в команде

Выбери действие ниже 👇
"""
    
    await message.answer(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu(WEBAPP_URL if WEBAPP_URL else None)
    )


@router.message(F.text == "⚙️ Настройки")
async def settings(message: Message):
    """Настройки"""
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Отправьте /start")
        return
    
    text = f"""
⚙️ **Настройки**

👤 **Ваш профиль:**
• Имя: {user['full_name']}
• Username: @{user['username'] or 'не указан'}
• ID: `{user['telegram_id']}`

🔔 Напоминания: Включены
"""
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Справка"""
    text = """
📖 **Справка**

**Команды:**
/start — Главное меню
/help — Эта справка

**Как пользоваться:**

1️⃣ Нажми "🏠 Пространства"
2️⃣ Выбери личное или создай команду
3️⃣ Создавай задачи
4️⃣ Ставь приоритеты и напоминания

**Приоритеты:**
🔴 Высокий
🟡 Средний  
🟢 Низкий

**Приглашение в команду:**
Отправь коллеге код приглашения!
"""
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "🔔 Напоминания")
async def show_reminders(message: Message):
    """Показать напоминания"""
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Отправьте /start")
        return
    
    reminders = await db.get_user_reminders(user["id"])
    
    if not reminders:
        await message.answer("🔔 **Напоминания**\n\n_У вас нет активных напоминаний_", parse_mode="Markdown")
        return
    
    text = "🔔 **Ваши напоминания:**\n\n"
    for r in reminders[:10]:
        text += f"• {r['task_title']}\n  ⏰ {r['remind_at']}\n\n"
    
    await message.answer(text, parse_mode="Markdown")
