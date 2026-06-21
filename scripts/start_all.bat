@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   JNAO - Start All Services
echo ========================================
echo [START] %time%
echo.

cd /d "%~dp0.."

REM --- First, stop any stale services ---
echo [INFO] Stopping stale services...
call "%~dp0stop_all.bat" -q

if not exist ".venv\Scripts\activate" (
    echo [ERROR] Virtual environment not found. Run: python -m venv .venv
    pause
    exit /b 1
)

call .venv\Scripts\activate

if not exist "logs" mkdir logs

REM ========================================
REM   Start Backend (background)
REM ========================================
echo [INFO] Starting backend...
cd backend

REM Write backend PID to file ourselves via a small wrapper
REM uvicorn --reload spawns a child, so we track the outer cmd PID
start "JNAO-Backend" /MIN cmd /c "cd /d \"%cd%\" && ..\.venv\Scripts\uvicorn.exe main:app --host 127.0.0.1 --port 8011 --reload > ..\logs\backend.log 2>&1"

REM Give the backend window a moment to spawn, then capture its PID
timeout /t 1 /nobreak >nul
for /f "tokens=2" %%i in ('tasklist /fi "WINDOWTITLE eq JNAO-Backend" /fo list 2^>nul ^| findstr /b "PID:"') do set BK_PID=%%i
if defined BK_PID (
    echo !BK_PID!>"..\logs\backend.pid"
    echo   [OK] Backend PID !BK_PID! starting...
) else (
    echo   [WARN] Could not capture backend PID
)

cd ..

REM --- Wait for backend to be ready ---
echo [INFO] Waiting for backend health check...
echo [TIME] backend poll start: %time%
for /L %%i in (1,1,20) do (
    curl -s -o NUL http://127.0.0.1:8011/health 2>nul
    if !errorlevel!==0 (
        echo [TIME] backend ready:      %time%
        goto :backend_ready
    )
    timeout /t 1 /nobreak >nul
)
echo   [WARN] Backend health check timed out — starting frontend anyway
:backend_ready

REM ========================================
REM   Start Frontend (foreground)
REM ========================================
echo [TIME] frontend start: %time%
echo [INFO] Starting frontend...
cd h5_fronted

if not exist "node_modules" (
    echo [INFO] Installing frontend dependencies...
    call npm install
)

echo.
echo   Backend:  http://127.0.0.1:8011
echo   Frontend: http://127.0.0.1:5185
echo   Ctrl+C to stop frontend, then run: scripts\stop_all.bat
echo ========================================
echo.

call npm run dev

REM --- Cleanup after frontend exits ---
echo.
echo [INFO] Frontend stopped. Cleaning up...
cd ..
call "%~dp0stop_all.bat"
