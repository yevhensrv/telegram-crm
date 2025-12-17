@echo off
cd /d "C:\Projects\telegram-crm"

mkdir bot
mkdir bot\handlers
mkdir webapp

type nul > bot\__init__.py
type nul > bot\main.py
type nul > bot\config.py
type nul > bot\database.py
type nul > bot\keyboards.py

type nul > bot\handlers\__init__.py
type nul > bot\handlers\start.py
type nul > bot\handlers\tasks.py
type nul > bot\handlers\workspaces.py
type nul > bot\handlers\reminders.py

type nul > webapp\index.html
type nul > webapp\style.css
type nul > webapp\app.js

type nul > .env
type nul > requirements.txt
type nul > README.md

echo.
echo ? Структура создана!
pause