"""
База данных CRM с автоматическим исправлением ошибок
"""

import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict
import secrets
import logging

DATABASE_PATH = "crm_database.db"

async def check_and_update_schema():
    """
    Авто-исправление: Добавляет недостающие колонки, если они пропали.
    Это лечит ошибку "no such column: custom_role".
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Список колонок, которые обязательно должны быть в таблице
        required_columns = [
            ("workspace_members", "custom_role", "TEXT"),
            ("workspace_members", "can_edit_tasks", "BOOLEAN DEFAULT TRUE"),
            ("workspace_members", "can_delete_tasks", "BOOLEAN DEFAULT FALSE"),
            ("workspace_members", "can_assign_tasks", "BOOLEAN DEFAULT FALSE"),
            ("workspace_members", "can_manage_members", "BOOLEAN DEFAULT FALSE"),
        ]
        
        for table, column, col_type in required_columns:
            try:
                # Проверяем, существует ли колонка
                await db.execute(f"SELECT {column} FROM {table} LIMIT 1")
            except Exception:
                # Если колонки нет - добавляем её
                try:
                    await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                    await db.commit()
                    print(f"✅ Добавлена отсутствующая колонка: {column} в таблицу {table}")
                except Exception as e:
                    print(f"❌ Не удалось добавить колонку {column}: {e}")

async def init_database():
    """Создаём таблицы и проверяем их структуру"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        
        # Пользователи
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Пространства
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
        
        # Участники пространств
        await db.execute("""
            CREATE TABLE IF NOT EXISTS workspace_members (
                id INTEGER PRIMARY KEY,
                workspace_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT DEFAULT 'member',
                custom_role TEXT,
                can_edit_tasks BOOLEAN DEFAULT TRUE,
                can_delete_tasks BOOLEAN DEFAULT FALSE,
                can_assign_tasks BOOLEAN DEFAULT FALSE,
                can_manage_members BOOLEAN DEFAULT FALSE,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(workspace_id, user_id)
            )
        """)
        
        # Воронки
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
        
        # Этапы воронки
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
        
        # Задачи
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
                due_date TEXT,
                due_time TEXT,
                created_by INTEGER NOT NULL,
                assigned_to INTEGER,
                assigned_username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (funnel_id) REFERENCES funnels(id),
                FOREIGN KEY (stage_id) REFERENCES funnel_stages(id),
                FOREIGN KEY (created_by) REFERENCES users(id),
                FOREIGN KEY (assigned_to) REFERENCES users(id)
            )
        """)
        
        # Напоминания
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
        
        # Заметки
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY,
                workspace_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                note_date TEXT,
                color TEXT DEFAULT '#ffc107',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        await db.commit()
        # Комментарии к задачам (НОВАЯ ТАБЛИЦА)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS task_comments (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                comment_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
    # СРАЗУ ПОСЛЕ создания запускаем проверку на новые колонки
    await check_and_update_schema()
    print("✅ База данных готова и проверена!")


# ==================== ПОЛЬЗОВАТЕЛИ ====================

async def create_user(telegram_id: int, username: str = None, full_name: str = None) -> int:
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
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_by_username(username: str) -> Optional[Dict]:
    """Найти пользователя по username"""
    clean_username = username.replace('@', '').strip()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE username = ?", (clean_username,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_by_id(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# ==================== ПРОСТРАНСТВА ====================

async def create_workspace(name: str, owner_id: int, is_personal: bool = False, description: str = None) -> int:
    invite_code = secrets.token_urlsafe(8) if not is_personal else None
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO workspaces (name, description, owner_id, is_personal, invite_code) VALUES (?, ?, ?, ?, ?)",
            (name, description, owner_id, is_personal, invite_code)
        )
        workspace_id = cursor.lastrowid
        
        # Владелец - полные права
        await db.execute("""
            INSERT INTO workspace_members 
            (workspace_id, user_id, role, can_edit_tasks, can_delete_tasks, can_assign_tasks, can_manage_members)
            VALUES (?, ?, 'owner', TRUE, TRUE, TRUE, TRUE)
        """, (workspace_id, owner_id))
        
        # Базовая воронка
        cursor = await db.execute(
            "INSERT INTO funnels (workspace_id, name, color) VALUES (?, 'Основная', '#3498db')",
            (workspace_id,)
        )
        funnel_id = cursor.lastrowid
        
        # Этапы
        stages = [("📥 Новые", 0, "#e74c3c"), ("🔄 В работе", 1, "#f39c12"), ("✅ Готово", 2, "#27ae60")]
        for stage_name, position, color in stages:
            await db.execute(
                "INSERT INTO funnel_stages (funnel_id, name, position, color) VALUES (?, ?, ?, ?)",
                (funnel_id, stage_name, position, color)
            )
        
        await db.commit()
        return workspace_id


async def create_personal_workspace(user_id: int) -> int:
    return await create_workspace("🏠 Личное пространство", user_id, True, "Ваши личные задачи")


async def get_user_workspaces(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT w.*, wm.role, wm.custom_role, wm.can_edit_tasks, wm.can_delete_tasks, 
                   wm.can_assign_tasks, wm.can_manage_members
            FROM workspaces w
            JOIN workspace_members wm ON w.id = wm.workspace_id
            WHERE wm.user_id = ?
            ORDER BY w.is_personal DESC, w.created_at ASC
        """, (user_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_workspace(workspace_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_workspace_members(workspace_id: int) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT u.*, wm.role, wm.custom_role, wm.can_edit_tasks, wm.can_delete_tasks,
                   wm.can_assign_tasks, wm.can_manage_members, wm.joined_at
            FROM users u
            JOIN workspace_members wm ON u.id = wm.user_id
            WHERE wm.workspace_id = ?
            ORDER BY wm.role DESC, wm.joined_at ASC
        """, (workspace_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def add_member_to_workspace(workspace_id: int, user_id: int, role: str = 'member', 
                                   custom_role: str = None, permissions: dict = None) -> bool:
    """Добавить участника в пространство"""
    perms = permissions or {}
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute("""
                INSERT INTO workspace_members 
                (workspace_id, user_id, role, custom_role, can_edit_tasks, can_delete_tasks, 
                 can_assign_tasks, can_manage_members)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                workspace_id, user_id, role, custom_role,
                perms.get('can_edit_tasks', True),
                perms.get('can_delete_tasks', False),
                perms.get('can_assign_tasks', False),
                perms.get('can_manage_members', False)
            ))
            await db.commit()
            return True
        except:
            return False


async def update_member_role(workspace_id: int, user_id: int, role: str = None, 
                              custom_role: str = None, permissions: dict = None) -> bool:
    """Обновить роль участника"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        updates = []
        params = []
        
        if role:
            updates.append("role = ?")
            params.append(role)
        if custom_role is not None:
            updates.append("custom_role = ?")
            params.append(custom_role)
        if permissions:
            for key, value in permissions.items():
                updates.append(f"{key} = ?")
                params.append(value)
        
        if not updates:
            return False
        
        params.extend([workspace_id, user_id])
        query = f"UPDATE workspace_members SET {', '.join(updates)} WHERE workspace_id = ? AND user_id = ?"
        
        await db.execute(query, params)
        await db.commit()
        return True


async def remove_member_from_workspace(workspace_id: int, user_id: int) -> bool:
    """Удалить участника из пространства"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, user_id)
        )
        await db.commit()
        return True


async def join_workspace_by_code(user_id: int, invite_code: str) -> Optional[int]:
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


# ==================== ВОРОНКИ ====================

async def get_funnels(workspace_id: int) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM funnels WHERE workspace_id = ? ORDER BY position", (workspace_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_funnel_stages(funnel_id: int) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM funnel_stages WHERE funnel_id = ? ORDER BY position", (funnel_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def create_funnel(workspace_id: int, name: str) -> int:
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

async def create_task(workspace_id: int, title: str, created_by: int, 
                      description: str = None, priority: str = "medium",
                      due_date: str = None, due_time: str = None,
                      assigned_to: int = None, assigned_username: str = None) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
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
            INSERT INTO tasks 
            (workspace_id, funnel_id, stage_id, title, description, priority, 
             due_date, due_time, created_by, assigned_to, assigned_username)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (workspace_id, funnel_id, stage_id, title, description, priority, 
              due_date, due_time, created_by, assigned_to, assigned_username))
        
        await db.commit()
        return cursor.lastrowid


async def get_tasks(workspace_id: int, stage_id: int = None) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        if stage_id:
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE workspace_id = ? AND stage_id = ? ORDER BY priority DESC, created_at DESC",
                (workspace_id, stage_id)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE workspace_id = ? ORDER BY priority DESC, created_at DESC", 
                (workspace_id,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_task(task_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_task(task_id: int, **kwargs) -> bool:
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
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM reminders WHERE task_id = ?", (task_id,))
        await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await db.commit()
        return True


# ==================== НАПОМИНАНИЯ ====================

async def create_reminder(task_id: int, user_id: int, remind_at: datetime) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO reminders (task_id, user_id, remind_at) VALUES (?, ?, ?)",
            (task_id, user_id, remind_at)
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_reminders() -> List[Dict]:
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
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE reminders SET is_sent = TRUE WHERE id = ?", (reminder_id,))
        await db.commit()
        return True


async def get_user_reminders(user_id: int) -> List[Dict]:
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


# ==================== ЗАМЕТКИ ====================

async def create_note(workspace_id: int, user_id: int, title: str, 
                      content: str = None, note_date: str = None, color: str = '#ffc107') -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO notes (workspace_id, user_id, title, content, note_date, color)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (workspace_id, user_id, title, content, note_date, color))
        await db.commit()
        return cursor.lastrowid


async def get_notes(workspace_id: int, note_date: str = None) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        if note_date:
            cursor = await db.execute(
                "SELECT * FROM notes WHERE workspace_id = ? AND note_date = ? ORDER BY created_at DESC",
                (workspace_id, note_date)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM notes WHERE workspace_id = ? ORDER BY created_at DESC",
                (workspace_id,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_note(note_id: int, **kwargs) -> bool:
    if not kwargs:
        return False
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        set_clause = ", ".join(f"{key} = ?" for key in kwargs.keys())
        await db.execute(
            f"UPDATE notes SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            list(kwargs.values()) + [note_id]
        )
        await db.commit()
        return True


async def delete_note(note_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        await db.commit()
        return True

# ==================== КОММЕНТАРИИ К ЗАДАЧАМ ====================

async def add_task_comment(task_id: int, user_id: int, comment_text: str) -> int:
    """Добавить новый комментарий к задаче."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO task_comments (task_id, user_id, comment_text) VALUES (?, ?, ?)",
            (task_id, user_id, comment_text)
        )
        await db.commit()
        return cursor.lastrowid

async def get_task_comments(task_id: int) -> List[Dict]:
    """Получить все комментарии для задачи, включая информацию о пользователе."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT tc.*, u.username, u.full_name
            FROM task_comments tc
            JOIN users u ON tc.user_id = u.id
            WHERE tc.task_id = ?
            ORDER BY tc.created_at ASC
        """, (task_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
