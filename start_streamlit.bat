@echo off
chcp 65001 >nul
title OCC-Web Streamlit Dashboard Launcher
cd /d "%~dp0"

echo ======================================================
echo   OCC-Web Streamlit Dashboard を起動しています...
echo ======================================================
echo.

set "VENV_PYTHON=system\.venv\Scripts\python.exe"
set "VENV_STREAMLIT=system\.venv\Scripts\streamlit.exe"

if not exist "%VENV_PYTHON%" (
    echo [INFO] Python 仮想環境を作成しています...
    python -m venv system\.venv
    if errorlevel 1 (
        echo [ERROR] 仮想環境の作成に失敗しました。Python 3.10以上がインストールされているか確認してください。
        pause
        exit /b 1
    )
    echo [INFO] 必要なライブラリをインストールしています...
    "%VENV_PYTHON%" -m pip install --upgrade pip
    "%VENV_PYTHON%" -m pip install -r requirements.txt
)

echo [INFO] Streamlit ダッシュボードを起動中 (http://localhost:8501)...
start http://localhost:8501
"%VENV_STREAMLIT%" run system\streamlit_app.py --server.port 8501 --server.headless true

pause


