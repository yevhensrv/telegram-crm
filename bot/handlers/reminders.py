# Файл: bot/handlers/reminders.py
"""
Напоминания
"""

from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot import database as db
from bot.keyboards import get_reminder_keyboard, get_task_menu

router = Router()


@router.callback_query(F.data.startswith("remind:"))
async def callback_remind(callback: CallbackQuery):
    """Показать варианты напоминания"""
    task_id = int(callback.data.split(":")[1])
    
    await callback.message.edit_text(
        "🔔 **Когда напомнить?**",
        parse_mode="Markdown",
        reply_markup=get_reminder_keyboard(task_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("remindme:"))
async def callback_set_reminder(callback: CallbackQuery):
    """Установка напоминания"""
    parts = callback.data.split(":")
    task_id = int(parts[1])
    time_option = parts[2]
    
    user = await db.get_user(callback.from_user.id)
    task = await db.get_task(task_id)
    
    if not user or not task:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    now = datetime.now()
    
    if time_option == "tomorrow":
        remind_at = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    else:
        minutes = int(time_option)
        remind_at = now + timedelta(minutes=minutes)
    
    await db.create_reminder(task_id, user["id"], remind_at)
    
    time_str = remind_at.strftime("%d.%m.%Y %H:%M")
    await callback.answer(f"✅ Напомню {time_str}", show_alert=True)
    
    priority_names = {"high": "🔴 Высокий", "medium": "🟡 Средний", "low": "🟢 Низкий"}
    status_names = {"todo": "⬜ Не начата", "in_progress": "🔄 В работе", "done": "✅ Выполнена"}
    
    text = f"""
📋 **{task['title']}**

{task.get('description') or '_Без описания_'}

**Статус:** {status_names.get(task.get('status', 'todo'), '⬜ Не начата')}
**Приоритет:** {priority_names.get(task.get('priority', 'medium'), '🟡 Средний')}
🔔 **Напоминание:** {time_str}
"""
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_task_menu(task_id, task['workspace_id'])
    )
