"""
Работа с базой данных
Здесь храним пользователей, задачи, пространства
"""

import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict
import secrets

DATABASE_PATH = "crm_database.db"


async def init_database():
    """Создаём все таблицы в базе данных"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        
        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица пространств (личные и командные)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                owner_id INTEGER NOT NULL,
                is_personal BOOLEAN DEFAULT FALSE,
                invite_code TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )
        """)
        
        # Таблица участников пространств
        await db.execute("""
            CREATE TABLE IF NOT EXISTS workspace_members (
                id INTEGER PRIMARY KEY,
                workspace_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT DEFAULT 'member',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(workspace_id, user_id)
            )
        """)
        
        # Таблица воронок
        await db.execute("""
            CREATE TABLE IF NOT EXISTS funnels (
                id INTEGER PRIMARY KEY,
                workspace_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                color TEXT DEFAULT '#3498db',
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            )
        """)
        
        # Таблица этапов воронки
        await db.execute("""
            CREATE TABLE IF NOT EXISTS funnel_stages (
                id INTEGER PRIMARY KEY,
                funnel_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                position INTEGER DEFAULT 0,
                color TEXT DEFAULT '#95a5a6',
                FOREIGN KEY (funnel_id) REFERENCES funnels(id)
            )
        """)
        
        # Таблица задач
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                workspace_id INTEGER NOT NULL,
                funnel_id INTEGER,
                stage_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'todo',
                due_date TIMESTAMP,
                created_by INTEGER NOT NULL,
                assigned_to INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (funnel_id) REFERENCES funnels(id),
                FOREIGN KEY (stage_id) REFERENCES funnel_stages(id),
                FOREIGN KEY (created_by) REFERENCES users(id),
                FOREIGN KEY (assigned_to) REFERENCES users(id)
            )
        """)
        
        # Таблица напоминаний
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                remind_at TIMESTAMP NOT NULL,
                is_sent BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Таблица трекинга времени
        await db.execute("""
            CREATE TABLE IF NOT EXISTS time_entries (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                started_at TIMESTAMP NOT NULL,
                ended_at TIMESTAMP,
                duration_minutes INTEGER,
                description TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        await db.commit()
        print("✅ База данных готова!")


# ==================== ПОЛЬЗОВАТЕЛИ ====================

async def create_user(telegram_id: int, username: str = None, full_name: str = None) -> int:
    """Создаём нового пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, full_name) VALUES (?, ?, ?)",
            (telegram_id, username, full_name)
        )
        await db.commit()
        
        cursor = await db.execute(
            "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        return row[0]


async def get_user(telegram_id: int) -> Optional[Dict]:
    """Получаем пользователя по Telegram ID"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# ==================== ПРОСТРАНСТВА ====================

async def create_workspace(name: str, owner_id: int, is_personal: bool = False, description: str = None) -> int:
    """Создаём новое пространство"""
    invite_code = secrets.token_urlsafe(8) if not is_personal else None
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO workspaces (name, description, owner_id, is_personal, invite_code) VALUES (?, ?, ?, ?, ?)",
            (name, description, owner_id, is_personal, invite_code)
        )
        workspace_id = cursor.lastrowid
        
        # Добавляем владельца как участника
        await db.execute(
            "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, 'owner')",
            (workspace_id, owner_id)
        )
        
        # Создаём базовую воронку
        cursor = await db.execute(
            "INSERT INTO funnels (workspace_id, name, color) VALUES (?, 'Основная', '#3498db')",
            (workspace_id,)
        )
        funnel_id = cursor.lastrowid
        
        # Создаём этапы воронки
        stages = [("📥 Новые", 0, "#e74c3c"), ("🔄 В работе", 1, "#f39c12"), ("✅ Готово", 2, "#27ae60")]
        for stage_name, position, color in stages:
            await db.execute(
                "INSERT INTO funnel_stages (funnel_id, name, position, color) VALUES (?, ?, ?, ?)",
                (funnel_id, stage_name, position, color)
            )
        
        await db.commit()
        return workspace_id


async def create_personal_workspace(user_id: int) -> int:
    """Создаём личное пространство"""
    return await create_workspace("🏠 Личное пространство", user_id, True, "Ваши личные задачи")


async def get_user_workspaces(user_id: int) -> List[Dict]:
    """Получаем все пространства пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT w.*, wm.role FROM workspaces w
            JOIN workspace_members wm ON w.id = wm.workspace_id
            WHERE wm.user_id = ?
            ORDER BY w.is_personal DESC, w.created_at ASC
        """, (user_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_workspace(workspace_id: int) -> Optional[Dict]:
    """Получаем пространство по ID"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def join_workspace_by_code(user_id: int, invite_code: str) -> Optional[int]:
    """Присоединяемся к пространству по коду"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT id FROM workspaces WHERE invite_code = ?", (invite_code,))
        row = await cursor.fetchone()
        
        if not row:
            return None
        
        workspace_id = row[0]
        await db.execute(
            "INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, 'member')",
            (workspace_id, user_id)
        )
        await db.commit()
        return workspace_id


async def get_workspace_members(workspace_id: int) -> List[Dict]:
    """Получаем участников пространства"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT u.*, wm.role FROM users u
            JOIN workspace_members wm ON u.id = wm.user_id
            WHERE wm.workspace_id = ?
        """, (workspace_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ==================== ВОРОНКИ ====================

async def get_funnels(workspace_id: int) -> List[Dict]:
    """Получаем воронки пространства"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM funnels WHERE workspace_id = ? ORDER BY position", (workspace_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_funnel_stages(funnel_id: int) -> List[Dict]:
    """Получаем этапы воронки"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM funnel_stages WHERE funnel_id = ? ORDER BY position", (funnel_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def create_funnel(workspace_id: int, name: str) -> int:
    """Создаём воронку"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO funnels (workspace_id, name) VALUES (?, ?)", (workspace_id, name)
        )
        funnel_id = cursor.lastrowid
        
        stages = [("📥 Новые", 0), ("🔄 В работе", 1), ("✅ Готово", 2)]
        for stage_name, position in stages:
            await db.execute(
                "INSERT INTO funnel_stages (funnel_id, name, position) VALUES (?, ?, ?)",
                (funnel_id, stage_name, position)
            )
        await db.commit()
        return funnel_id


# ==================== ЗАДАЧИ ====================

async def create_task(workspace_id: int, title: str, created_by: int, description: str = None,
                      priority: str = "medium", due_date: datetime = None, assigned_to: int = None) -> int:
    """Создаём задачу"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Получаем первую воронку и этап
        cursor = await db.execute(
            "SELECT id FROM funnels WHERE workspace_id = ? LIMIT 1", (workspace_id,)
        )
        funnel_row = await cursor.fetchone()
        funnel_id = funnel_row[0] if funnel_row else None
        
        stage_id = None
        if funnel_id:
            cursor = await db.execute(
                "SELECT id FROM funnel_stages WHERE funnel_id = ? ORDER BY position LIMIT 1", (funnel_id,)
            )
            stage_row = await cursor.fetchone()
            stage_id = stage_row[0] if stage_row else None
        
        cursor = await db.execute("""
            INSERT INTO tasks (workspace_id, funnel_id, stage_id, title, description, priority, due_date, created_by, assigned_to)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (workspace_id, funnel_id, stage_id, title, description, priority, due_date, created_by, assigned_to))
        
        await db.commit()
        return cursor.lastrowid


async def get_tasks(workspace_id: int, stage_id: int = None) -> List[Dict]:
    """Получаем задачи"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        if stage_id:
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE workspace_id = ? AND stage_id = ? ORDER BY priority DESC",
                (workspace_id, stage_id)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE workspace_id = ? ORDER BY priority DESC", (workspace_id,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_task(task_id: int) -> Optional[Dict]:
    """Получаем задачу"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_task(task_id: int, **kwargs) -> bool:
    """Обновляем задачу"""
    if not kwargs:
        return False
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        set_clause = ", ".join(f"{key} = ?" for key in kwargs.keys())
        await db.execute(
            f"UPDATE tasks SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            list(kwargs.values()) + [task_id]
        )
        await db.commit()
        return True


async def delete_task(task_id: int) -> bool:
    """Удаляем задачу"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM reminders WHERE task_id = ?", (task_id,))
        await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await db.commit()
        return True


# ==================== НАПОМИНАНИЯ ====================

async def create_reminder(task_id: int, user_id: int, remind_at: datetime) -> int:
    """Создаём напоминание"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO reminders (task_id, user_id, remind_at) VALUES (?, ?, ?)",
            (task_id, user_id, remind_at)
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_reminders() -> List[Dict]:
    """Получаем напоминания для отправки"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT r.*, t.title as task_title, u.telegram_id
            FROM reminders r
            JOIN tasks t ON r.task_id = t.id
            JOIN users u ON r.user_id = u.id
            WHERE r.is_sent = FALSE AND r.remind_at <= datetime('now')
        """)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def mark_reminder_sent(reminder_id: int) -> bool:
    """Отмечаем напоминание как отправленное"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE reminders SET is_sent = TRUE WHERE id = ?", (reminder_id,))
        await db.commit()
        return True


async def get_user_reminders(user_id: int) -> List[Dict]:
    """Получаем напоминания пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT r.*, t.title as task_title FROM reminders r
            JOIN tasks t ON r.task_id = t.id
            WHERE r.user_id = ? AND r.is_sent = FALSE
            ORDER BY r.remind_at ASC
        """, (user_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]