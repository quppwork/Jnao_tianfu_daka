$ErrorActionPreference = "SilentlyContinue"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  JNAO - 停止全部服务" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

& "$PSScriptRoot\kill_port.ps1" -Ports @(8012, 5185)

Write-Host "  全部服务已停止" -ForegroundColor Green
Write-Host ""
