@echo off
chcp 65001 >nul

echo ========================================
echo   JNAO - Vue Frontend
echo ========================================

cd /d "%~dp0..\vue_fronted"

if not exist "node_modules" (
    echo [INFO] Installing dependencies...
    call npm install
)

echo [INFO] Starting on http://127.0.0.1:5185
echo.
call npm run dev
pause
