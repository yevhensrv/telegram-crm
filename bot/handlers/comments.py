# Файл: bot/handlers/comments.py
"""
Комментарии к задачам
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.database import add_task_comment, get_task_comments, get_task, get_user
from bot.keyboards import back_to_task_kb
from datetime import datetime

router = Router()


class CommentStates(StatesGroup):
    waiting_for_comment_text = State()


def format_comment(comment: dict) -> str:
    """Форматирует один комментарий для вывода."""
    try:
        timestamp = datetime.strptime(comment['created_at'], '%Y-%m-%d %H:%M:%S').strftime('%d.%m %H:%M')
    except (ValueError, TypeError):
        timestamp = "Н/Д"

    if comment.get('username'):
        author = f"@{comment['username']}"
    else:
        author = comment.get('full_name', 'Пользователь')
        
    return f"**{author}** ({timestamp}):\n{comment['comment_text']}\n"


# ================= Хэндлер просмотра комментариев =================
@router.callback_query(F.data.startswith("view_comments_"))
async def view_comments(call: CallbackQuery, state: FSMContext):
    await call.answer()

    task_id = int(call.data.split("_")[-1])

    user_db = await get_user(call.from_user.id)
    if not user_db:
        await call.message.edit_text("❌ Пользователь не найден. Отправьте /start")
        return
        
    comments = await get_task_comments(task_id)
    task = await get_task(task_id)

    if not task:
        await call.message.edit_text("❌ Задача не найдена.")
        return

    text = f"💬 **Комментарии к задаче:**\n📋 {task['title']}\n\n"

    if comments:
        for comment in comments:
            text += format_comment(comment) + "—" * 20 + "\n"
    else:
        text += "_Нет комментариев._"

    kb = back_to_task_kb(task_id)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


# ================= Хэндлер начала добавления комментария =================
@router.callback_query(F.data.startswith("add_comment_"))
async def start_add_comment(call: CallbackQuery, state: FSMContext):
    await call.answer()
    task_id = int(call.data.split("_")[-1])

    await state.update_data(task_to_comment=task_id)
    await state.set_state(CommentStates.waiting_for_comment_text)

    await call.message.edit_text(
        "✍️ Введите текст комментария:\n\n_Или отправьте /cancel для отмены_",
        parse_mode="Markdown"
    )


# ================= Хэндлер отмены =================
@router.message(CommentStates.waiting_for_comment_text, F.text == "/cancel")
async def cancel_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get('task_to_comment')
    await state.clear()
    
    if task_id:
        await message.answer("❌ Отменено", reply_markup=back_to_task_kb(task_id))
    else:
        await message.answer("❌ Отменено")


# ================= Хэндлер сохранения комментария =================
@router.message(CommentStates.waiting_for_comment_text)
async def process_comment_text(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get('task_to_comment')

    user_data = await get_user(message.from_user.id)

    if not user_data:
        await message.answer("❌ Ошибка авторизации. Отправьте /start")
        await state.clear()
        return

    db_user_id = user_data['id']
    comment_text = message.text

    if not task_id:
        await message.answer("❌ Произошла ошибка. Попробуйте начать сначала.")
        await state.clear()
        return

    await add_task_comment(task_id=task_id, user_id=db_user_id, comment_text=comment_text)
    await state.clear()

    await message.answer("✅ Комментарий добавлен!", reply_markup=back_to_task_kb(task_id))
