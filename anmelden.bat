@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
.venv\Scripts\python.exe telegram_anmelden.py
echo.
pause
