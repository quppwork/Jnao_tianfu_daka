@echo off
chcp 65001 >nul
echo ========================================
echo   JNAO - 数据库备份
echo ========================================
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\backup_db.ps1"
pause
