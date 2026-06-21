@echo off
chcp 65001 >nul
echo ========================================
echo   JNAO H5 Frontend - Vite Dev Server
echo ========================================
echo [START] %time%
echo.

cd /d "%~dp0..\h5_fronted"

if not exist "node_modules" (
    echo [INFO] Installing dependencies...
    call npm install
)

echo [TIME] vite start: %time%
echo [INFO] Starting frontend on http://127.0.0.1:5185
echo.

call npm run dev

pause
