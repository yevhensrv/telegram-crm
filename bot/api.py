"""
API для Mini App
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import os

from bot import database as db

# Создаём API
app = FastAPI(title="CRM Mini App")

# Разрешаем запросы отовсюду
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Путь к webapp
WEBAPP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "webapp")


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

@app.get("/", response_class=HTMLResponse)
async def index():
    filepath = os.path.join(WEBAPP_DIR, "index.html")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Mini App</h1>")


@app.get("/style.css")
async def get_css():
    filepath = os.path.join(WEBAPP_DIR, "style.css")
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="text/css")
    raise HTTPException(status_code=404)


@app.get("/app.js")
async def get_js():
    filepath = os.path.join(WEBAPP_DIR, "app.js")
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="application/javascript")
    raise HTTPException(status_code=404)


# ==================== API ПОЛЬЗОВАТЕЛЯ ====================

@app.get("/api/user/{telegram_id}")
async def get_user(telegram_id: int):
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

@app.get("/api/workspace/{workspace_id}")
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


@app.get("/api/workspace/{workspace_id}/members")
async def get_members(workspace_id: int):
    """Получить участников пространства"""
    members = await db.get_workspace_members(workspace_id)
    return {"members": members}


@app.post("/api/workspace/{workspace_id}/members")
async def add_member(workspace_id: int, member: MemberAdd):
    """Добавить участника по username"""
    # Находим пользователя по username
    user = await db.get_user_by_username(member.username)
    
    if not user:
        raise HTTPException(status_code=404, detail=f"Пользователь @{member.username} не найден. Он должен сначала написать боту /start")
    
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
    
    members = await db.get_workspace_members(workspace_id)
    return {"success": True, "members": members}


@app.put("/api/workspace/{workspace_id}/members/{user_id}")
async def update_member(workspace_id: int, user_id: int, member: MemberUpdate):
    """Обновить роль участника"""
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


@app.delete("/api/workspace/{workspace_id}/members/{user_id}")
async def remove_member(workspace_id: int, user_id: int):
    """Удалить участника"""
    await db.remove_member_from_workspace(workspace_id, user_id)
    members = await db.get_workspace_members(workspace_id)
    return {"success": True, "members": members}


# ==================== API ЗАДАЧ ====================

@app.post("/api/tasks/{workspace_id}/{telegram_id}")
async def create_task(workspace_id: int, telegram_id: int, task: TaskCreate):
    """Создать задачу"""
    user = await db.get_user(telegram_id)
    if not user:
        raise HTTPException(status_code=404)
    
    # Если указан username для назначения
    assigned_to = None
    if task.assigned_username:
        assigned_user = await db.get_user_by_username(task.assigned_username)
        if assigned_user:
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
        assigned_username=task.assigned_username.replace('@', '') if task.assigned_username else None
    )
    
    return {"task": await db.get_task(task_id)}


@app.put("/api/task/{task_id}")
async def update_task(task_id: int, task: TaskUpdate):
    """Обновить задачу"""
    data = {}
    
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
    if task.assigned_username is not None:
        clean_username = task.assigned_username.replace('@', '') if task.assigned_username else None
        data["assigned_username"] = clean_username
        
        # Находим user_id по username
        if clean_username:
            assigned_user = await db.get_user_by_username(clean_username)
            if assigned_user:
                data["assigned_to"] = assigned_user["id"]
        else:
            data["assigned_to"] = None
    
    if data:
        await db.update_task(task_id, **data)
    
    return {"task": await db.get_task(task_id)}


@app.delete("/api/task/{task_id}")
async def delete_task(task_id: int):
    """Удалить задачу"""
    await db.delete_task(task_id)
    return {"success": True}


@app.post("/api/task/{task_id}/toggle")
async def toggle_task(task_id: int):
    """Переключить статус задачи"""
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404)
    
    new_status = "todo" if task.get("status") == "done" else "done"
    await db.update_task(task_id, status=new_status)
    return {"task": await db.get_task(task_id)}


@app.post("/api/task/{task_id}/move/{stage_id}")
async def move_task(task_id: int, stage_id: int):
    """Переместить задачу"""
    await db.update_task(task_id, stage_id=stage_id)
    return {"task": await db.get_task(task_id)}


@app.post("/api/task/{task_id}/assign")
async def assign_task(task_id: int, username: str):
    """Назначить задачу на пользователя"""
    clean_username = username.replace('@', '')
    
    user = await db.get_user_by_username(clean_username)
    assigned_to = user["id"] if user else None
    
    await db.update_task(task_id, assigned_username=clean_username, assigned_to=assigned_to)
    return {"task": await db.get_task(task_id)}


# ==================== API ЗАМЕТОК ====================

@app.get("/api/notes/{workspace_id}")
async def get_notes(workspace_id: int, date: Optional[str] = None):
    """Получить заметки"""
    notes = await db.get_notes(workspace_id, date)
    return {"notes": notes}


@app.post("/api/notes/{workspace_id}/{telegram_id}")
async def create_note(workspace_id: int, telegram_id: int, note: NoteCreate):
    """Создать заметку"""
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


@app.put("/api/note/{note_id}")
async def update_note(note_id: int, note: NoteUpdate):
    """Обновить заметку"""
    data = {k: v for k, v in note.dict().items() if v is not None}
    if data:
        await db.update_note(note_id, **data)
    
    return {"success": True}


@app.delete("/api/note/{note_id}")
async def delete_note(note_id: int):
    """Удалить заметку"""
    await db.delete_note(note_id)
    return {"success": True}


# ==================== ПРЕДУСТАНОВЛЕННЫЕ РОЛИ ====================

@app.get("/api/roles/presets")
async def get_role_presets():
    """Получить предустановленные роли"""
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
                "name": "НП (Начальник производства)",
                "description": "Полный доступ к управлению",
                "can_edit_tasks": True,
                "can_delete_tasks": True,
                "can_assign_tasks": True,
                "can_manage_members": True
            },
            {
                "id": "team_lead",
                "name": "СК (Старший команды)",
                "description": "Управление задачами и участниками",
                "can_edit_tasks": True,
                "can_delete_tasks": True,
                "can_assign_tasks": True,
                "can_manage_members": True
            },
            {
                "id": "admin",
                "name": "А (Админ)",
                "description": "Управление участниками и дедлайнами",
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
