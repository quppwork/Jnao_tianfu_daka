@echo off
chcp 65001 >nul

set NO_PAUSE=0
if "%~1"=="-q" set NO_PAUSE=1
if "%~1"=="--quiet" set NO_PAUSE=1

echo ========================================
echo   JNAO - Stop All Services
echo ========================================
echo.

cd /d "%~dp0.."

REM --- Kill by PID file ---
if exist "logs\backend.pid" (
    set /p BK_PID=<"logs\backend.pid"
    echo [INFO] Stopping backend PID !BK_PID!...
    taskkill /PID !BK_PID! /F /T 2>nul
    del "logs\backend.pid" 2>nul
    echo   [OK] Backend stopped
) else (
    echo   [WARN] No PID file for backend
)

REM --- Clean ports ---
echo [INFO] Cleaning port 8011...
powershell -ExecutionPolicy Bypass -File "%~dp0kill_port.ps1" 8011

echo [INFO] Cleaning port 5185...
powershell -ExecutionPolicy Bypass -File "%~dp0kill_port.ps1" 5185

echo.
echo   All services stopped.

if "%NO_PAUSE%"=="0" pause
exit /b 0
