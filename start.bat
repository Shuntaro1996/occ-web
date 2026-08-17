@echo off
setlocal
cd /d "%~dp0"

title OCC-Web Launcher

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10+ is not found.
    pause
    exit /b 1
)

if not exist "system\.venv\Scripts\python.exe" (
    echo [SETUP] Creating Python virtual environment...
    python -m venv system\.venv
    system\.venv\Scripts\pip.exe install -r system\backend\requirements.txt -q
)

start "" /d "%~dp0system" "%~dp0system\.venv\Scripts\pythonw.exe" backend\app.py
ping 127.0.0.1 -n 3 >nul
start http://localhost:5000
exit