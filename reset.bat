@echo off
chcp 65001 >nul
echo ========================================
echo   JNAO - 清空本地数据
echo ========================================
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\reset_local_data.ps1"
pause
