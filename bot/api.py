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

from bot import database as db

# -------------------------------------------------------------
# 1. ОСНОВНОЕ FASTAPI ПРИЛОЖЕНИЕ (для запуска Uvicorn)
# -------------------------------------------------------------
api_app = FastAPI(title="CRM Mini App") # ПЕРЕИМЕНОВАНО в api_app

# Разрешаем запросы отовсюду
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# 2. РОУТЕР ДЛЯ API ЭНДПОИНТОВ (для подключения к боту в main.py)
# -------------------------------------------------------------
router = APIRouter() # НОВЫЙ ОБЪЕКТ, КОТОРЫЙ ИМПОРТИРУЕТ main.py

# Путь к webapp
WEBAPP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "webapp")


# ==================== МОДЕЛИ ====================
# (Оставляем твои модели без изменений)
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    assigned_username: Optional[str] = None
# ... (и так далее, все твои остальные модели)
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
# Эти хэндлеры привязываем к api_app, а не к router

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


# ==================== API ЭНДПОИНТЫ (ПРИВЯЗЫВАЕМ К router) ====================

@router.get("/user/{telegram_id}") # Было @app.get, стало @router.get
async def get_user_data(telegram_id: int): # Переименовано, чтобы не конфликтовать с db.get_user
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


# ... (ПОВТОРИТЕ ЭТО ДЛЯ ВСЕХ ОСТАЛЬНЫХ ЭНДПОИНТОВ, ЗАМЕНЯЯ @app.get/post/put/delete НА @router.get/post/put/delete) ...

# === Остальные API (Workspace, Tasks, Notes, Roles) ===
# Просто замените @app. на @router. в каждом хэндлере ниже.
# Например:
# Было: @app.get("/api/workspace/{workspace_id}/members")
# Стало: @router.get("/workspace/{workspace_id}/members")
# *Удаляем "/api" из роутера, так как он будет добавлен в main.py*

# Я привел только начало, но тебе нужно заменить @app. на @router. ВО ВСЕХ ФУНКЦИЯХ API!

# ... (ПРИМЕР ДЛЯ СЛЕДУЮЩЕЙ ФУНКЦИИ)

@router.get("/workspace/{workspace_id}/members") 
async def get_members(workspace_id: int):
    """Получить участников пространства"""
    members = await db.get_workspace_members(workspace_id)
    return {"members": members}
    
# ... (ПРОДОЛЖАЙТЕ ДЛЯ ВСЕГО ФАЙЛА)
# ...

# ==================== КОНЕЦ ФАЙЛА ====================

# Важно: Все API-маршруты, которые были @app.get("/api/..."),
# должны стать @router.get("/..."), поскольку префикс "/api" 
# мы добавим в main.py
