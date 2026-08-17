@echo off
setlocal
cd /d "%~dp0"

title OCC-Web Launcher

python --version >nul 2>&1
if errorlevel 1 (
    echo ======================================================================
    echo  [エラー] Python が見つかりません。
    echo  Python 3.10 以上がインストールされているか、PATH に追加されているか
    echo  ご確認ください。
    echo.
    echo  ※ インストール時は必ず「Add python.exe to PATH」にチェックを入れてください。
    echo  ダウンロード: https://www.python.org/downloads/
    echo ======================================================================
    echo.
    pause
    exit /b 1
)


if not exist "system\.venv\Scripts\python.exe" (
    echo [SETUP] Creating Python virtual environment...
    python -m venv system\.venv
    system\.venv\Scripts\pip.exe install -r requirements.txt -q
)


start "" /d "%~dp0system" "%~dp0system\.venv\Scripts\pythonw.exe" backend\app.py
ping 127.0.0.1 -n 3 >nul
start http://localhost:5000
exit