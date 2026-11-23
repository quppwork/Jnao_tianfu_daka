@echo off
chcp 65001 >nul
powershell -ExecutionPolicy Bypass -File "%~dp0start_all.ps1"
pause
