"""
Клавиатуры и кнопки бота
"""

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def get_main_menu(webapp_url: str = None) -> ReplyKeyboardMarkup:
    """Главное меню бота"""
    builder = ReplyKeyboardBuilder()
    
    if webapp_url:
        builder.add(KeyboardButton(
            text="📱 Открыть CRM",
            web_app=WebAppInfo(url=webapp_url)
        ))
    
    builder.add(KeyboardButton(text="📋 Мои задачи"))
    builder.add(KeyboardButton(text="🏠 Пространства"))
    builder.add(KeyboardButton(text="➕ Новая задача"))
    builder.add(KeyboardButton(text="🔔 Напоминания"))
    builder.add(KeyboardButton(text="⚙️ Настройки"))
    
    builder.adjust(1, 2, 2)
    return builder.as_markup(resize_keyboard=True)


def get_workspaces_keyboard(workspaces: list) -> InlineKeyboardMarkup:
    """Клавиатура выбора пространства"""
    builder = InlineKeyboardBuilder()
    
    for ws in workspaces:
        icon = "🏠" if ws.get("is_personal") else "👥"
        builder.add(InlineKeyboardButton(
            text=f"{icon} {ws['name']}",
            callback_data=f"ws:{ws['id']}"
        ))
    
    builder.add(InlineKeyboardButton(text="➕ Создать команду", callback_data="ws:create"))
    builder.add(InlineKeyboardButton(text="🔗 Присоединиться", callback_data="ws:join"))
    
    builder.adjust(1)
    return builder.as_markup()


def get_workspace_menu(workspace_id: int, is_personal: bool = False) -> InlineKeyboardMarkup:
    """Меню пространства"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(text="📋 Задачи", callback_data=f"tasks:{workspace_id}"))
    builder.add(InlineKeyboardButton(text="📊 Воронка", callback_data=f"funnel:{workspace_id}"))
    builder.add(InlineKeyboardButton(text="➕ Новая задача", callback_data=f"newtask:{workspace_id}"))
    
    if not is_personal:
        builder.add(InlineKeyboardButton(text="👥 Участники", callback_data=f"members:{workspace_id}"))
        builder.add(InlineKeyboardButton(text="🔗 Пригласить", callback_data=f"invite:{workspace_id}"))
    
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="ws:list"))
    
    builder.adjust(2, 1, 2, 1)
    return builder.as_markup()


def get_tasks_keyboard(tasks: list, workspace_id: int) -> InlineKeyboardMarkup:
    """Список задач"""
    builder = InlineKeyboardBuilder()
    
    priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    
    for task in tasks[:10]:
        icon = priority_icons.get(task.get("priority", "medium"), "⚪")
        status_icon = "✅" if task.get("status") == "done" else ""
        title = task["title"][:25] + "..." if len(task["title"]) > 25 else task["title"]
        builder.add(InlineKeyboardButton(
            text=f"{status_icon}{icon} {title}",
            callback_data=f"task:{task['id']}"
        ))
    
    builder.add(InlineKeyboardButton(text="➕ Новая задача", callback_data=f"newtask:{workspace_id}"))
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data=f"ws:{workspace_id}"))
    
    builder.adjust(1)
    return builder.as_markup()


def get_task_menu(task_id: int, workspace_id: int) -> InlineKeyboardMarkup:
    """Меню задачи"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(text="✏️ Изменить", callback_data=f"edit:{task_id}"))
    builder.add(InlineKeyboardButton(text="🔄 Этап", callback_data=f"stage:{task_id}"))
    builder.add(InlineKeyboardButton(text="⚡ Приоритет", callback_data=f"priority:{task_id}"))
    builder.add(InlineKeyboardButton(text="🔔 Напомнить", callback_data=f"remind:{task_id}"))
    builder.add(InlineKeyboardButton(text="✅ Выполнено", callback_data=f"done:{task_id}"))
    builder.add(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete:{task_id}"))
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data=f"tasks:{workspace_id}"))
    
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def get_priority_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Выбор приоритета"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(text="🔴 Высокий", callback_data=f"setprio:{task_id}:high"))
    builder.add(InlineKeyboardButton(text="🟡 Средний", callback_data=f"setprio:{task_id}:medium"))
    builder.add(InlineKeyboardButton(text="🟢 Низкий", callback_data=f"setprio:{task_id}:low"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"task:{task_id}"))
    
    builder.adjust(3, 1)
    return builder.as_markup()


def get_stages_keyboard(stages: list, task_id: int) -> InlineKeyboardMarkup:
    """Выбор этапа"""
    builder = InlineKeyboardBuilder()
    
    for stage in stages:
        builder.add(InlineKeyboardButton(
            text=stage["name"],
            callback_data=f"setstage:{task_id}:{stage['id']}"
        ))
    
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"task:{task_id}"))
    
    builder.adjust(1)
    return builder.as_markup()


def get_reminder_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Выбор времени напоминания"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(text="⏰ 15 мин", callback_data=f"remindme:{task_id}:15"))
    builder.add(InlineKeyboardButton(text="⏰ 30 мин", callback_data=f"remindme:{task_id}:30"))
    builder.add(InlineKeyboardButton(text="⏰ 1 час", callback_data=f"remindme:{task_id}:60"))
    builder.add(InlineKeyboardButton(text="⏰ 3 часа", callback_data=f"remindme:{task_id}:180"))
    builder.add(InlineKeyboardButton(text="📅 Завтра 9:00", callback_data=f"remindme:{task_id}:tomorrow"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"task:{task_id}"))
    
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def get_confirm_delete_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_del:{task_id}"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"task:{task_id}"))
    
    builder.adjust(2)
    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()