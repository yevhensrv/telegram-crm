"""
API для Mini App
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
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


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    stage_id: Optional[int] = None


# ==================== СТРАНИЦЫ ====================

@app.get("/", response_class=HTMLResponse)
async def index():
    """Главная страница"""
    filepath = os.path.join(WEBAPP_DIR, "index.html")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Mini App</h1>")


@app.get("/style.css")
async def get_css():
    """CSS стили"""
    filepath = os.path.join(WEBAPP_DIR, "style.css")
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="text/css")
    raise HTTPException(status_code=404)


@app.get("/app.js")
async def get_js():
    """JavaScript"""
    filepath = os.path.join(WEBAPP_DIR, "app.js")
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="application/javascript")
    raise HTTPException(status_code=404)


# ==================== API ПОЛЬЗОВАТЕЛЯ ====================

@app.get("/api/user/{telegram_id}")
async def get_user(telegram_id: int):
    """Получить пользователя"""
    user = await db.get_user(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    workspaces = await db.get_user_workspaces(user["id"])
    
    # Статистика
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
    """Получить пространство с данными"""
    workspace = await db.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404)
    
    tasks = await db.get_tasks(workspace_id)
    funnels = await db.get_funnels(workspace_id)
    
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
        "tasks": tasks
    }


# ==================== API ЗАДАЧ ====================

@app.post("/api/tasks/{workspace_id}/{telegram_id}")
async def create_task(workspace_id: int, telegram_id: int, task: TaskCreate):
    """Создать задачу"""
    user = await db.get_user(telegram_id)
    if not user:
        raise HTTPException(status_code=404)
    
    task_id = await db.create_task(
        workspace_id=workspace_id,
        title=task.title,
        created_by=user["id"],
        description=task.description,
        priority=task.priority
    )
    
    return {"task": await db.get_task(task_id)}


@app.put("/api/task/{task_id}")
async def update_task(task_id: int, task: TaskUpdate):
    """Обновить задачу"""
    data = {k: v for k, v in task.dict().items() if v is not None}
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