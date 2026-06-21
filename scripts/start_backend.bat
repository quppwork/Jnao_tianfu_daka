@echo off
chcp 65001 >nul
echo ========================================
echo   JNAO Backend - FastAPI Server
echo ========================================
echo [START] %time%
echo.

cd /d "%~dp0.."

if not exist ".venv\Scripts\activate" (
    echo [ERROR] Virtual environment not found. Run: python -m venv .venv
    pause
    exit /b 1
)

echo [TIME] venv activate start: %time%
call .venv\Scripts\activate
echo [TIME] venv activate done:  %time%

echo [INFO] Cleaning port 8011...
powershell -ExecutionPolicy Bypass -File "%~dp0kill_port.ps1" 8011

cd backend

echo [TIME] uvicorn start: %time%
echo [INFO] Starting backend on http://127.0.0.1:8011
echo [INFO] API docs: http://127.0.0.1:8011/docs
echo.

uvicorn main:app --host 127.0.0.1 --port 8011 --reload

pause
