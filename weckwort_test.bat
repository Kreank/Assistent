@echo off
chcp 65001 >nul
cd /d "%~dp0"
.venv\Scripts\python.exe weckwort_test.py
pause
