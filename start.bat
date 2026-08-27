@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

title OCC-Web Launcher

echo ======================================================================
echo   OCC-Web (Orlaco EMOS Camera Configurator GUI) を起動しています...
echo ======================================================================
echo.

:: 1. Python の存在確認
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

:: 2. 仮想環境の存在確認・初期化
if not exist "system\.venv\Scripts\python.exe" (
    echo [SETUP] Python 仮想環境を作成しています (初回のみ)...
    python -m venv system\.venv
    if errorlevel 1 (
        echo [エラー] 仮想環境の作成に失敗しました。
        pause
        exit /b 1
    )
    echo [SETUP] 必要なライブラリをインストールしています...
    system\.venv\Scripts\pip.exe install -r requirements.txt
    if errorlevel 1 (
        echo [エラー] パッケージのインストールに失敗しました。
        pause
        exit /b 1
    )
)

:: 3. サーバー起動
echo [INFO] バックエンドサーバー (Waitress) を起動しています...
set "LOG_FILE=%~dp0system\server.log"

:: バックグラウンド起動（ログを system\server.log に出力）
start "OCC-Web Server" /min /d "%~dp0system" "%~dp0system\.venv\Scripts\python.exe" backend\app.py

:: サーバーの起動待機（最大10秒間、ポート5000の応答を待つ）
echo [INFO] サーバーの準備完了を待機しています...
set "RETRY_COUNT=0"

:WAIT_LOOP
set /a RETRY_COUNT+=1
powershell -NoProfile -Command "try { $res = Invoke-WebRequest -Uri 'http://localhost:5000/api/status' -UseBasicParsing -TimeoutSec 1; if ($res.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if %errorlevel% equ 0 (
    goto SERVER_READY
)

if %RETRY_COUNT% geq 10 (
    echo.
    echo [警告] サーバーの応答待機がタイムアウトしました。
    echo 起動ログを確認してください: %LOG_FILE%
    echo そのままブラウザを開きます...
    goto OPEN_BROWSER
)

timeout /t 1 /nobreak >nul
goto WAIT_LOOP

:SERVER_READY
echo [OK] サーバーが正常に起動しました！ (http://localhost:5000)

:OPEN_BROWSER
start http://localhost:5000
echo.
echo ======================================================================
echo   OCC-Web はバックグラウンドで正常に稼働しています。
echo   ブラウザを閉じると自動的にサーバーも終了します。
echo ======================================================================
echo.
timeout /t 3 >nul
exit