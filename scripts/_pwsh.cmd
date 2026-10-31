@echo off
REM Prefer PowerShell 7 (pwsh); fall back to Windows PowerShell 5.1
where pwsh >nul 2>&1
if %ERRORLEVEL%==0 (
  pwsh -NoProfile -ExecutionPolicy Bypass %*
  exit /b %ERRORLEVEL%
)
powershell -NoProfile -ExecutionPolicy Bypass %*
exit /b %ERRORLEVEL%
