"""
Инициализация обработчиков
"""

from bot.handlers import start, tasks, workspaces, reminders

# Список всех роутеров
routers = [
    start.router,
    workspaces.router,
    tasks.router,
    reminders.router,
]