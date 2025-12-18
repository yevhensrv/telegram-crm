# Файл: bot/handlers/routers.py

from aiogram import Router
from . import start
from . import tasks
from . import workspaces
from . import reminders
from . import comments # НОВЫЙ ХЭНДЛЕР

# Создаем главный роутер, который соберет все остальные
main_router = Router()

# Включаем все роутеры в главный
main_router.include_router(start.router)
main_router.include_router(workspaces.router)
main_router.include_router(tasks.router)
main_router.include_router(reminders.router)
main_router.include_router(comments.router)

# Мы возвращаем main_router, чтобы импортировать его в main.py
