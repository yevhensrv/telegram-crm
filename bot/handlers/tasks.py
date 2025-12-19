# Файл: bot/handlers/tasks.py
"""
Управление задачами
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot import database as db
from bot.keyboards import (
    get_tasks_keyboard, 
    get_task_menu,
    get_priority_keyboard,
    get_stages_keyboard,
    get_confirm_delete_keyboard,
    get_main_menu
)
from bot.config import WEBAPP_URL

logger = logging.getLogger(__name__)
router = Router()


class TaskStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_workspace_select = State()
    editing_title = State()
    editing_description = State()


# ==================== ПОКАЗАТЬ ЗАДАЧИ ====================

@router.message(F.text == "📋 Мои задачи")
async def show_my_tasks(message: Message):
    """Показать задачи из личного пространства"""
    logger.info(f"=== SHOW MY TASKS from {message.from_user.id} ===")
    
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Отправьте /start")
        return
    
    workspaces = await db.get_user_workspaces(user["id"])
    personal = next((ws for ws in workspaces if ws.get("is_personal")), None)
    
    if not personal:
        await message.answer("❌ Личное пространство не найдено")
        return
    
    tasks = await db.get_tasks(personal["id"])
    
    if not tasks:
        text = "📋 **Мои задачи**\n\n_Пока нет задач. Создайте первую!_"
    else:
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        text = "📋 **Мои задачи:**\n\n"
        
        for task in tasks[:15]:
            icon = priority_icons.get(task.get("priority", "medium"), "⚪")
            status = "✅" if task.get("status") == "done" else "⬜"
            text += f"{status} {icon} {task['title']}\n"
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_tasks_keyboard(tasks, personal["id"])
    )


@router.callback_query(F.data.startswith("tasks:"))
async def callback_tasks(callback: CallbackQuery):
    """Список задач пространства"""
    logger.info(f"=== CALLBACK TASKS: {callback.data} ===")
    
    workspace_id = int(callback.data.split(":")[1])
    tasks = await db.get_tasks(workspace_id)
    workspace = await db.get_workspace(workspace_id)
    
    if not tasks:
        text = f"📋 **{workspace['name']}**\n\n_Нет задач_"
    else:
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        text = f"📋 **{workspace['name']}**\n\n"
        
        for task in tasks[:15]:
            icon = priority_icons.get(task.get("priority", "medium"), "⚪")
            status = "✅" if task.get("status") == "done" else "⬜"
            text += f"{status} {icon} {task['title']}\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_tasks_keyboard(tasks, workspace_id)
    )
    await callback.answer()


# ==================== СОЗДАНИЕ ЗАДАЧИ ====================

@router.message(F.text == "➕ Новая задача")
async def new_task_start(message: Message, state: FSMContext):
    """Начало создания задачи"""
    logger.info(f"=== NEW TASK BUTTON from {message.from_user.id} ===")
    
    user = await db.get_user(message.from_user.id)
    if not user:
        logger.warning("User not found!")
        await message.answer("❌ Отправьте /start")
        return
    
    workspaces = await db.get_user_workspaces(user["id"])
    personal = next((ws for ws in workspaces if ws.get("is_personal")), None)
    
    if personal:
        await state.update_data(workspace_id=personal["id"])
        await message.answer(
            "📝 **Новая задача**\n\nВведите название задачи:",
            parse_mode="Markdown"
        )
        await state.set_state(TaskStates.waiting_title)
        logger.info("State set to waiting_title")
    else:
        logger.warning("No personal workspace!")
        await message.answer("❌ Личное пространство не найдено. Отправьте /start")


@router.callback_query(F.data.startswith("newtask:"))
async def callback_new_task(callback: CallbackQuery, state: FSMContext):
    """Создание задачи в конкретном пространстве"""
    logger.info(f"=== CALLBACK NEW TASK: {callback.data} ===")
    
    workspace_id = int(callback.data.split(":")[1])
    await state.update_data(workspace_id=workspace_id)
    
    await callback.message.edit_text(
        "📝 **Новая задача**\n\nВведите название:",
        parse_mode="Markdown"
    )
    await state.set_state(TaskStates.waiting_title)
    await callback.answer()


@router.message(TaskStates.waiting_title)
async def process_task_title(message: Message, state: FSMContext):
    """Получаем название задачи"""
    logger.info(f"=== TASK TITLE: {message.text} ===")
    
    await state.update_data(title=message.text)
    
    await message.answer(
        "📝 Введите описание задачи\n(или `-` чтобы пропустить):",
        parse_mode="Markdown"
    )
    await state.set_state(TaskStates.waiting_description)


@router.message(TaskStates.waiting_description)
async def process_task_description(message: Message, state: FSMContext):
    """Создаём задачу"""
    logger.info(f"=== TASK DESCRIPTION: {message.text} ===")
    
    data = await state.get_data()
    title = data["title"]
    workspace_id = data["workspace_id"]
    description = None if message.text == "-" else message.text
    
    user = await db.get_user(message.from_user.id)
    
    task_id = await db.create_task(
        workspace_id=workspace_id,
        title=title,
        created_by=user["id"],
        description=description
    )
    
    logger.info(f"=== TASK CREATED: {task_id} ===")
    
    await message.answer(
        f"✅ **Задача создана!**\n\n"
        f"📋 {title}\n"
        f"🟡 Приоритет: Средний\n"
        f"📥 Этап: Новые",
        parse_mode="Markdown",
        reply_markup=get_main_menu(WEBAPP_URL if WEBAPP_URL else None)
    )
    await state.clear()


# ==================== ПРОСМОТР ЗАДАЧИ ====================

@router.callback_query(F.data.startswith("task:"))
async def callback_task(callback: CallbackQuery):
    """Просмотр задачи"""
    logger.info(f"=== VIEW TASK: {callback.data} ===")
    
    task_id = int(callback.data.split(":")[1])
    task = await db.get_task(task_id)
    
    if not task:
        await callback.answer("❌ Задача не найдена", show_alert=True)
        return
    
    priority_names = {"high": "🔴 Высокий", "medium": "🟡 Средний", "low": "🟢 Низкий"}
    status_names = {"todo": "⬜ Не начата", "in_progress": "🔄 В работе", "done": "✅ Выполнена"}
    
    text = f"""
📋 **{task['title']}**

{task.get('description') or '_Без описания_'}

**Статус:** {status_names.get(task.get('status', 'todo'), '⬜ Не начата')}
**Приоритет:** {priority_names.get(task.get('priority', 'medium'), '🟡 Средний')}
"""
    
    if task.get('due_date'):
        text += f"**Срок:** {task['due_date']}\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_task_menu(task_id, task['workspace_id'])
    )
    await callback.answer()


# ==================== РЕДАКТИРОВАНИЕ ====================

@router.callback_query(F.data.startswith("edit:"))
async def callback_edit(callback: CallbackQuery, state: FSMContext):
    """Редактировать название"""
    logger.info(f"=== EDIT TASK: {callback.data} ===")
    
    task_id = int(callback.data.split(":")[1])
    await state.update_data(editing_task_id=task_id)
    
    await callback.message.edit_text(
        "✏️ **Редактирование**\n\nВведите новое название:",
        parse_mode="Markdown"
    )
    await state.set_state(TaskStates.editing_title)
    await callback.answer()


@router.message(TaskStates.editing_title)
async def process_edit_title(message: Message, state: FSMContext):
    """Сохраняем новое название"""
    logger.info(f"=== EDIT TITLE: {message.text} ===")
    
    data = await state.get_data()
    task_id = data["editing_task_id"]
    
    await db.update_task(task_id, title=message.text)
    task = await db.get_task(task_id)
    
    await message.answer(
        f"✅ Название изменено!\n\n📋 {message.text}",
        parse_mode="Markdown",
        reply_markup=get_task_menu(task_id, task['workspace_id'])
    )
    await state.clear()


# ==================== ПРИОРИТЕТ ====================

@router.callback_query(F.data.startswith("priority:"))
async def callback_priority(callback: CallbackQuery):
    """Выбор приоритета"""
    logger.info(f"=== PRIORITY: {callback.data} ===")
    
    task_id = int(callback.data.split(":")[1])
    
    await callback.message.edit_text(
        "⚡ **Выберите приоритет:**",
        parse_mode="Markdown",
        reply_markup=get_priority_keyboard(task_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("setprio:"))
async def callback_set_priority(callback: CallbackQuery):
    """Установка приоритета"""
    logger.info(f"=== SET PRIORITY: {callback.data} ===")
    
    parts = callback.data.split(":")
    task_id = int(parts[1])
    priority = parts[2]
    
    await db.update_task(task_id, priority=priority)
    
    priority_names = {"high": "🔴 Высокий", "medium": "🟡 Средний", "low": "🟢 Низкий"}
    await callback.answer(f"✅ Приоритет: {priority_names[priority]}", show_alert=True)
    
    task = await db.get_task(task_id)
    status_names = {"todo": "⬜ Не начата", "in_progress": "🔄 В работе", "done": "✅ Выполнена"}
    
    text = f"""
📋 **{task['title']}**

{task.get('description') or '_Без описания_'}

**Статус:** {status_names.get(task.get('status', 'todo'), '⬜ Не начата')}
**Приоритет:** {priority_names.get(priority, '🟡 Средний')}
"""
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_task_menu(task_id, task['workspace_id'])
    )


# ==================== ЭТАПЫ ВОРОНКИ ====================

@router.callback_query(F.data.startswith("stage:"))
async def callback_stage(callback: CallbackQuery):
    """Выбор этапа"""
    logger.info(f"=== STAGE: {callback.data} ===")
    
    task_id = int(callback.data.split(":")[1])
    task = await db.get_task(task_id)
    
    if not task or not task.get("funnel_id"):
        await callback.answer("❌ Воронка не найдена", show_alert=True)
        return
    
    stages = await db.get_funnel_stages(task["funnel_id"])
    
    await callback.message.edit_text(
        "🔄 **Выберите этап:**",
        parse_mode="Markdown",
        reply_markup=get_stages_keyboard(stages, task_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("setstage:"))
async def callback_set_stage(callback: CallbackQuery):
    """Установка этапа"""
    logger.info(f"=== SET STAGE: {callback.data} ===")
    
    parts = callback.data.split(":")
    task_id = int(parts[1])
    stage_id = int(parts[2])
    
    await db.update_task(task_id, stage_id=stage_id)
    await callback.answer("✅ Этап изменён!", show_alert=True)
    
    task = await db.get_task(task_id)
    priority_names = {"high": "🔴 Высокий", "medium": "🟡 Средний", "low": "🟢 Низкий"}
    status_names = {"todo": "⬜ Не начата", "in_progress": "🔄 В работе", "done": "✅ Выполнена"}
    
    text = f"""
📋 **{task['title']}**

{task.get('description') or '_Без описания_'}

**Статус:** {status_names.get(task.get('status', 'todo'), '⬜ Не начата')}
**Приоритет:** {priority_names.get(task.get('priority', 'medium'), '🟡 Средний')}
"""
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_task_menu(task_id, task['workspace_id'])
    )


# ==================== ВЫПОЛНЕНИЕ ====================

@router.callback_query(F.data.startswith("done:"))
async def callback_done(callback: CallbackQuery):
    """Отметить как выполненную"""
    logger.info(f"=== DONE: {callback.data} ===")
    
    task_id = int(callback.data.split(":")[1])
    task = await db.get_task(task_id)
    
    new_status = "todo" if task.get("status") == "done" else "done"
    await db.update_task(task_id, status=new_status)
    
    if new_status == "done":
        await callback.answer("✅ Задача выполнена!", show_alert=True)
    else:
        await callback.answer("⬜ Задача открыта заново", show_alert=True)
    
    task = await db.get_task(task_id)
    priority_names = {"high": "🔴 Высокий", "medium": "🟡 Средний", "low": "🟢 Низкий"}
    status_names = {"todo": "⬜ Не начата", "in_progress": "🔄 В работе", "done": "✅ Выполнена"}
    
    text = f"""
📋 **{task['title']}**

{task.get('description') or '_Без описания_'}

**Статус:** {status_names.get(task.get('status', 'todo'), '⬜ Не начата')}
**Приоритет:** {priority_names.get(task.get('priority', 'medium'), '🟡 Средний')}
"""
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_task_menu(task_id, task['workspace_id'])
    )


# ==================== УДАЛЕНИЕ ====================

@router.callback_query(F.data.startswith("delete:"))
async def callback_delete(callback: CallbackQuery):
    """Подтверждение удаления"""
    logger.info(f"=== DELETE: {callback.data} ===")
    
    task_id = int(callback.data.split(":")[1])
    task = await db.get_task(task_id)
    
    await callback.message.edit_text(
        f"🗑 **Удалить задачу?**\n\n📋 {task['title']}",
        parse_mode="Markdown",
        reply_markup=get_confirm_delete_keyboard(task_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del:"))
async def callback_confirm_delete(callback: CallbackQuery):
    """Удаление задачи"""
    logger.info(f"=== CONFIRM DELETE: {callback.data} ===")
    
    task_id = int(callback.data.split(":")[1])
    task = await db.get_task(task_id)
    workspace_id = task['workspace_id']
    
    await db.delete_task(task_id)
    await callback.answer("✅ Задача удалена!", show_alert=True)
    
    tasks = await db.get_tasks(workspace_id)
    workspace = await db.get_workspace(workspace_id)
    
    text = f"📋 **{workspace['name']}**\n\n"
    if not tasks:
        text += "_Нет задач_"
    else:
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        for t in tasks[:15]:
            icon = priority_icons.get(t.get("priority", "medium"), "⚪")
            status = "✅" if t.get("status") == "done" else "⬜"
            text += f"{status} {icon} {t['title']}\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_tasks_keyboard(tasks, workspace_id)
    )


# ==================== ВОРОНКА ====================

@router.callback_query(F.data.startswith("funnel:"))
async def callback_funnel(callback: CallbackQuery):
    """Показать воронку"""
    logger.info(f"=== FUNNEL: {callback.data} ===")
    
    workspace_id = int(callback.data.split(":")[1])
    funnels = await db.get_funnels(workspace_id)
    
    if not funnels:
        await callback.answer("❌ Воронки не найдены", show_alert=True)
        return
    
    funnel = funnels[0]
    stages = await db.get_funnel_stages(funnel["id"])
    
    text = f"📊 **{funnel['name']}**\n\n"
    
    for stage in stages:
        tasks = await db.get_tasks(workspace_id, stage_id=stage["id"])
        text += f"**{stage['name']}** ({len(tasks)})\n"
        
        for task in tasks[:5]:
            priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            icon = priority_icons.get(task.get("priority", "medium"), "⚪")
            text += f"  {icon} {task['title'][:20]}\n"
        
        if len(tasks) > 5:
            text += f"  _...и ещё {len(tasks) - 5}_\n"
        text += "\n"
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data=f"ws:{workspace_id}"))
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


# ==================== ОТМЕНА ====================

@router.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена действия"""
    logger.info(f"=== CANCEL ===")
    
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено")
    await callback.answer()
