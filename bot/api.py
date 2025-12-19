# Файл: bot/api.py
"""
API для Mini App
"""

from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import os
import logging

from bot import database as db

logger = logging.getLogger(__name__)

# -------------------------------------------------------------
# 1. ОСНОВНОЕ FASTAPI ПРИЛОЖЕНИЕ
# -------------------------------------------------------------
api_app = FastAPI(title="CRM Mini App")

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# 2. РОУТЕР ДЛЯ API ЭНДПОИНТОВ
# -------------------------------------------------------------
router = APIRouter(prefix="/api")

WEBAPP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "webapp")


# ==================== ФУНКЦИЯ ОТПРАВКИ УВЕДОМЛЕНИЙ ====================

async def send_notification(telegram_id: int, text: str):
    """Отправить уведомление пользователю"""
    try:
        from bot.main import bot
        from aiogram.enums import ParseMode
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"Уведомление отправлено: {telegram_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")
        return False


# ==================== МОДЕЛИ ====================

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    assigned_username: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    stage_id: Optional[int] = None
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    assigned_username: Optional[str] = None


class MemberAdd(BaseModel):
    username: str
    role: str = "member"
    custom_role: Optional[str] = None
    can_edit_tasks: bool = True
    can_delete_tasks: bool = False
    can_assign_tasks: bool = False
    can_manage_members: bool = False


class MemberUpdate(BaseModel):
    role: Optional[str] = None
    custom_role: Optional[str] = None
    can_edit_tasks: Optional[bool] = None
    can_delete_tasks: Optional[bool] = None
    can_assign_tasks: Optional[bool] = None
    can_manage_members: Optional[bool] = None


class NoteCreate(BaseModel):
    title: str
    content: Optional[str] = None
    note_date: Optional[str] = None
    color: str = "#ffc107"


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    note_date: Optional[str] = None
    color: Optional[str] = None


# ==================== СТРАНИЦЫ ====================

@api_app.get("/", response_class=HTMLResponse)
async def index():
    filepath = os.path.join(WEBAPP_DIR, "index.html")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Mini App</h1>")


@api_app.get("/style.css")
async def get_css():
    filepath = os.path.join(WEBAPP_DIR, "style.css")
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="text/css")
    raise HTTPException(status_code=404)


@api_app.get("/app.js")
async def get_js():
    filepath = os.path.join(WEBAPP_DIR, "app.js")
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="application/javascript")
    raise HTTPException(status_code=404)


# ==================== API ПОЛЬЗОВАТЕЛЯ ====================

@router.get("/user/{telegram_id}")
async def get_user_data(telegram_id: int):
    user = await db.get_user(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    workspaces = await db.get_user_workspaces(user["id"])
    
    total = 0
    done = 0
    for ws in workspaces:
        tasks = await db.get_tasks(ws["id"])
        total += len(tasks)
        done += len([t for t in tasks if t.get("status") == "done"])
    
    return {
        "user": user,
        "workspaces": workspaces,
        "stats": {
            "total": total,
            "done": done
        }
    }


# ==================== API ПРОСТРАНСТВ ====================

@router.get("/workspace/{workspace_id}")
async def get_workspace(workspace_id: int):
    workspace = await db.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404)
    
    tasks = await db.get_tasks(workspace_id)
    funnels = await db.get_funnels(workspace_id)
    members = await db.get_workspace_members(workspace_id)
    
    result_funnels = []
    for funnel in funnels:
        stages = await db.get_funnel_stages(funnel["id"])
        stages_with_tasks = []
        for stage in stages:
            stage_tasks = [t for t in tasks if t.get("stage_id") == stage["id"]]
            stages_with_tasks.append({**stage, "tasks": stage_tasks})
        result_funnels.append({**funnel, "stages": stages_with_tasks})
    
    return {
        "workspace": workspace,
        "funnels": result_funnels,
        "tasks": tasks,
        "members": members
    }


@router.get("/workspace/{workspace_id}/members")
async def get_members(workspace_id: int):
    members = await db.get_workspace_members(workspace_id)
    return {"members": members}


@router.post("/workspace/{workspace_id}/members")
async def add_member(workspace_id: int, member: MemberAdd):
    user = await db.get_user_by_username(member.username)
    
    if not user:
        raise HTTPException(
            status_code=404, 
            detail=f"Пользователь @{member.username} не найден. Он должен сначала написать боту /start"
        )
    
    permissions = {
        "can_edit_tasks": member.can_edit_tasks,
        "can_delete_tasks": member.can_delete_tasks,
        "can_assign_tasks": member.can_assign_tasks,
        "can_manage_members": member.can_manage_members
    }
    
    success = await db.add_member_to_workspace(
        workspace_id, user["id"], member.role, member.custom_role, permissions
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Пользователь уже в команде")
    
    # Уведомляем пользователя о добавлении в команду
    workspace = await db.get_workspace(workspace_id)
    await send_notification(
        user["telegram_id"],
        f"👥 **Вас добавили в команду!**\n\n"
        f"📂 Пространство: {workspace['name']}\n"
        f"🎭 Роль: {member.custom_role or member.role}"
    )
    
    members = await db.get_workspace_members(workspace_id)
    return {"success": True, "members": members}


@router.put("/workspace/{workspace_id}/members/{user_id}")
async def update_member(workspace_id: int, user_id: int, member: MemberUpdate):
    permissions = {}
    if member.can_edit_tasks is not None:
        permissions["can_edit_tasks"] = member.can_edit_tasks
    if member.can_delete_tasks is not None:
        permissions["can_delete_tasks"] = member.can_delete_tasks
    if member.can_assign_tasks is not None:
        permissions["can_assign_tasks"] = member.can_assign_tasks
    if member.can_manage_members is not None:
        permissions["can_manage_members"] = member.can_manage_members
    
    await db.update_member_role(
        workspace_id, user_id, 
        role=member.role, 
        custom_role=member.custom_role,
        permissions=permissions if permissions else None
    )
    
    members = await db.get_workspace_members(workspace_id)
    return {"success": True, "members": members}


@router.delete("/workspace/{workspace_id}/members/{user_id}")
async def remove_member(workspace_id: int, user_id: int):
    await db.remove_member_from_workspace(workspace_id, user_id)
    members = await db.get_workspace_members(workspace_id)
    return {"success": True, "members": members}


# ==================== API ЗАДАЧ ====================

@router.post("/tasks/{workspace_id}/{telegram_id}")
async def create_task(workspace_id: int, telegram_id: int, task: TaskCreate):
    """Создать задачу"""
    user = await db.get_user(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    assigned_to = None
    assigned_user = None
    clean_username = None
    
    # Проверяем существование назначенного пользователя
    if task.assigned_username:
        clean_username = task.assigned_username.replace('@', '').strip()
        if clean_username:
            assigned_user = await db.get_user_by_username(clean_username)
            if not assigned_user:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Пользователь @{clean_username} не найден. Он должен сначала написать боту /start"
                )
            assigned_to = assigned_user["id"]
    
    task_id = await db.create_task(
        workspace_id=workspace_id,
        title=task.title,
        created_by=user["id"],
        description=task.description,
        priority=task.priority,
        due_date=task.due_date,
        due_time=task.due_time,
        assigned_to=assigned_to,
        assigned_username=clean_username
    )
    
    # Отправляем уведомление назначенному пользователю
    if assigned_user and assigned_user["telegram_id"] != telegram_id:
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        priority_icon = priority_icons.get(task.priority, "🟡")
        
        notification_text = (
            f"📋 **Вам назначена новая задача!**\n\n"
            f"**{task.title}**\n"
            f"{task.description or ''}\n\n"
            f"{priority_icon} Приоритет: {task.priority}\n"
            f"👤 От: @{user.get('username') or user.get('full_name', 'Пользователь')}"
        )
        
        if task.due_date:
            notification_text += f"\n📅 Срок: {task.due_date}"
            if task.due_time:
                notification_text += f" {task.due_time}"
        
        await send_notification(assigned_user["telegram_id"], notification_text)
    
    return {"task": await db.get_task(task_id)}


@router.put("/task/{task_id}")
async def update_task(task_id: int, task: TaskUpdate):
    """Обновить задачу"""
    old_task = await db.get_task(task_id)
    if not old_task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    data = {}
    assigned_user = None
    old_assigned_username = old_task.get("assigned_username")
    
    if task.title is not None:
        data["title"] = task.title
    if task.description is not None:
        data["description"] = task.description
    if task.priority is not None:
        data["priority"] = task.priority
    if task.status is not None:
        data["status"] = task.status
    if task.stage_id is not None:
        data["stage_id"] = task.stage_id
    if task.due_date is not None:
        data["due_date"] = task.due_date if task.due_date else None
    if task.due_time is not None:
        data["due_time"] = task.due_time if task.due_time else None
    
    # Проверяем назначение пользователя
    if task.assigned_username is not None:
        clean_username = task.assigned_username.replace('@', '').strip() if task.assigned_username else None
        data["assigned_username"] = clean_username
        
        if clean_username:
            assigned_user = await db.get_user_by_username(clean_username)
            if not assigned_user:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Пользователь @{clean_username} не найден. Он должен сначала написать боту /start"
                )
            data["assigned_to"] = assigned_user["id"]
        else:
            data["assigned_to"] = None
    
    if data:
        await db.update_task(task_id, **data)
    
    # Отправляем уведомление если назначен новый пользователь
    new_username = data.get("assigned_username")
    if assigned_user and new_username and new_username != old_assigned_username:
        priority = task.priority or old_task.get("priority", "medium")
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        priority_icon = priority_icons.get(priority, "🟡")
        
        task_title = task.title or old_task.get("title", "")
        task_desc = task.description if task.description is not None else old_task.get("description", "")
        
        notification_text = (
            f"📋 **Вам назначена задача!**\n\n"
            f"**{task_title}**\n"
            f"{task_desc or ''}\n\n"
            f"{priority_icon} Приоритет: {priority}"
        )
        
        due_date = task.due_date if task.due_date is not None else old_task.get("due_date")
        if due_date:
            due_time = task.due_time if task.due_time is not None else old_task.get("due_time", "")
            notification_text += f"\n📅 Срок: {due_date} {due_time or ''}".strip()
        
        await send_notification(assigned_user["telegram_id"], notification_text)
    
    return {"task": await db.get_task(task_id)}


@router.delete("/task/{task_id}")
async def delete_task(task_id: int):
    """Удалить задачу"""
    await db.delete_task(task_id)
    return {"success": True}


@router.post("/task/{task_id}/toggle")
async def toggle_task(task_id: int):
    """Переключить статус задачи"""
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404)
    
    new_status = "todo" if task.get("status") == "done" else "done"
    await db.update_task(task_id, status=new_status)
    return {"task": await db.get_task(task_id)}


@router.post("/task/{task_id}/move/{stage_id}")
async def move_task(task_id: int, stage_id: int):
    """Переместить задачу"""
    await db.update_task(task_id, stage_id=stage_id)
    return {"task": await db.get_task(task_id)}


# ==================== ПРОВЕРКА ПОЛЬЗОВАТЕЛЯ ====================

@router.get("/check-user/{username}")
async def check_user_exists(username: str):
    """Проверить существует ли пользователь"""
    clean_username = username.replace('@', '').strip()
    user = await db.get_user_by_username(clean_username)
    
    if user:
        return {
            "exists": True,
            "username": user.get("username"),
            "full_name": user.get("full_name")
        }
    else:
        return {
            "exists": False,
            "message": f"Пользователь @{clean_username} не найден. Он должен написать боту /start"
        }


# ==================== API ЗАМЕТОК ====================

@router.get("/notes/{workspace_id}")
async def get_notes(workspace_id: int, date: Optional[str] = None):
    notes = await db.get_notes(workspace_id, date)
    return {"notes": notes}


@router.post("/notes/{workspace_id}/{telegram_id}")
async def create_note(workspace_id: int, telegram_id: int, note: NoteCreate):
    user = await db.get_user(telegram_id)
    if not user:
        raise HTTPException(status_code=404)
    
    note_id = await db.create_note(
        workspace_id=workspace_id,
        user_id=user["id"],
        title=note.title,
        content=note.content,
        note_date=note.note_date,
        color=note.color
    )
    
    notes = await db.get_notes(workspace_id)
    return {"note_id": note_id, "notes": notes}


@router.put("/note/{note_id}")
async def update_note(note_id: int, note: NoteUpdate):
    data = {k: v for k, v in note.dict().items() if v is not None}
    if data:
        await db.update_note(note_id, **data)
    return {"success": True}


@router.delete("/note/{note_id}")
async def delete_note(note_id: int):
    await db.delete_note(note_id)
    return {"success": True}


# ==================== ПРЕДУСТАНОВЛЕННЫЕ РОЛИ ====================

@router.get("/roles/presets")
async def get_role_presets():
    return {
        "presets": [
            {
                "id": "pm",
                "name": "PM (Project Manager)",
                "description": "Полный доступ к управлению",
                "can_edit_tasks": True,
                "can_delete_tasks": True,
                "can_assign_tasks": True,
                "can_manage_members": True
            },
            {
                "id": "lead",
                "name": "Lead",
                "description": "Полный доступ к управлению",
                "can_edit_tasks": True,
                "can_delete_tasks": True,
                "can_assign_tasks": True,
                "can_manage_members": True
            },
            {
                "id": "admin",
                "name": "Админ",
                "description": "Управление участниками",
                "can_edit_tasks": True,
                "can_delete_tasks": False,
                "can_assign_tasks": True,
                "can_manage_members": True
            },
            {
                "id": "member",
                "name": "Участник",
                "description": "Базовые права",
                "can_edit_tasks": True,
                "can_delete_tasks": False,
                "can_assign_tasks": False,
                "can_manage_members": False
            }
        ]
    }
