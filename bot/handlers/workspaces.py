# Файл: bot/handlers/workspaces.py
"""
Управление пространствами
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot import database as db
from bot.keyboards import get_workspaces_keyboard, get_workspace_menu

router = Router()


class WorkspaceStates(StatesGroup):
    waiting_name = State()
    waiting_description = State()
    waiting_invite_code = State()


@router.message(F.text == "🏠 Пространства")
async def show_workspaces(message: Message):
    """Показать пространства"""
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Отправьте /start")
        return
    
    workspaces = await db.get_user_workspaces(user["id"])
    
    text = "📂 **Ваши пространства:**\n\n"
    for ws in workspaces:
        icon = "🏠" if ws.get("is_personal") else "👥"
        role = " (владелец)" if ws.get("role") == "owner" else ""
        text += f"{icon} {ws['name']}{role}\n"
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_workspaces_keyboard(workspaces)
    )


@router.callback_query(F.data == "ws:list")
async def callback_ws_list(callback: CallbackQuery):
    """Список пространств"""
    user = await db.get_user(callback.from_user.id)
    workspaces = await db.get_user_workspaces(user["id"])
    
    text = "📂 **Ваши пространства:**\n\n"
    for ws in workspaces:
        icon = "🏠" if ws.get("is_personal") else "👥"
        text += f"{icon} {ws['name']}\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_workspaces_keyboard(workspaces)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ws:"))
async def callback_workspace(callback: CallbackQuery, state: FSMContext):
    """Выбор пространства"""
    action = callback.data.split(":")[1]
    
    if action == "create":
        await callback.message.edit_text(
            "📝 **Создание команды**\n\nВведите название:",
            parse_mode="Markdown"
        )
        await state.set_state(WorkspaceStates.waiting_name)
        await callback.answer()
        return
    
    if action == "join":
        await callback.message.edit_text(
            "🔗 **Присоединение**\n\nВведите код приглашения:",
            parse_mode="Markdown"
        )
        await state.set_state(WorkspaceStates.waiting_invite_code)
        await callback.answer()
        return
    
    if action == "list":
        return
    
    # Открываем пространство
    workspace_id = int(action)
    workspace = await db.get_workspace(workspace_id)
    
    if not workspace:
        await callback.answer("❌ Не найдено", show_alert=True)
        return
    
    tasks = await db.get_tasks(workspace_id)
    done_count = len([t for t in tasks if t.get("status") == "done"])
    
    icon = "🏠" if workspace.get("is_personal") else "👥"
    text = f"""
{icon} **{workspace['name']}**

{workspace.get('description') or ''}

📊 **Статистика:**
• Всего задач: {len(tasks)}
• Выполнено: {done_count}
"""
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_workspace_menu(workspace_id, workspace.get("is_personal"))
    )
    await callback.answer()


@router.message(WorkspaceStates.waiting_name)
async def process_ws_name(message: Message, state: FSMContext):
    """Получаем название"""
    await state.update_data(name=message.text)
    await message.answer(
        "📝 Введите описание\n(или `-` чтобы пропустить):",
        parse_mode="Markdown"
    )
    await state.set_state(WorkspaceStates.waiting_description)


@router.message(WorkspaceStates.waiting_description)
async def process_ws_description(message: Message, state: FSMContext):
    """Создаём пространство"""
    data = await state.get_data()
    name = data["name"]
    description = None if message.text == "-" else message.text
    
    user = await db.get_user(message.from_user.id)
    workspace_id = await db.create_workspace(name, user["id"], False, description)
    workspace = await db.get_workspace(workspace_id)
    
    await message.answer(
        f"✅ **Команда создана!**\n\n"
        f"👥 {name}\n\n"
        f"🔗 Код приглашения:\n`{workspace['invite_code']}`\n\n"
        f"Отправьте код коллегам!",
        parse_mode="Markdown"
    )
    await state.clear()


@router.message(WorkspaceStates.waiting_invite_code)
async def process_invite_code(message: Message, state: FSMContext):
    """Присоединяемся по коду"""
    code = message.text.strip()
    user = await db.get_user(message.from_user.id)
    
    workspace_id = await db.join_workspace_by_code(user["id"], code)
    
    if not workspace_id:
        await message.answer("❌ **Код не найден**\n\nПроверьте и попробуйте снова.", parse_mode="Markdown")
        await state.clear()
        return
    
    workspace = await db.get_workspace(workspace_id)
    await message.answer(f"✅ **Вы присоединились!**\n\n👥 {workspace['name']}", parse_mode="Markdown")
    await state.clear()


@router.callback_query(F.data.startswith("invite:"))
async def callback_invite(callback: CallbackQuery):
    """Показать код приглашения"""
    workspace_id = int(callback.data.split(":")[1])
    workspace = await db.get_workspace(workspace_id)
    
    if workspace and workspace.get("invite_code"):
        await callback.message.answer(
            f"🔗 **Код приглашения:**\n\n`{workspace['invite_code']}`\n\nОтправьте коллегам!",
            parse_mode="Markdown"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("members:"))
async def callback_members(callback: CallbackQuery):
    """Показать участников"""
    workspace_id = int(callback.data.split(":")[1])
    members = await db.get_workspace_members(workspace_id)
    
    text = "👥 **Участники:**\n\n"
    for m in members:
        role = "👑" if m.get("role") == "owner" else "👤"
        name = m.get("full_name") or m.get("username") or "Без имени"
        text += f"{role} {name}\n"
    
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()
