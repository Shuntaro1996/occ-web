@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

title OCC-Web Debug Launcher

echo ======================================================================
echo   OCC-Web デバッグモード起動 (コンソール出力あり)
echo ======================================================================
echo.

if not exist "system\.venv\Scripts\python.exe" (
    echo [SETUP] 仮想環境を作成しています...
    python -m venv system\.venv
    system\.venv\Scripts\pip.exe install -r requirements.txt
)

echo [INFO] ブラウザを開きます: http://localhost:5000
start http://localhost:5000

echo [INFO] サーバーを実行中 (終了するには Ctrl+C を押してください)...
echo.
cd system
"%~dp0system\.venv\Scripts\python.exe" backend\app.py

echo.
echo ======================================================================
echo   サーバーが終了しました。
echo ======================================================================
pause
