@echo off
chcp 65001 >nul
cd /d "%~dp0"
.venv\Scripts\python.exe google_anmelden.py
echo.
pause
