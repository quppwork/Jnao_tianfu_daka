$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $root "backend"
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$logsDir = Join-Path $root "logs"

if (-not (Test-Path $pythonExe)) {
    Write-Host "[ERROR] 未找到虚拟环境: $pythonExe" -ForegroundColor Red
    Write-Host "请先执行: python -m venv .venv && pip install -r backend/requirements.txt" -ForegroundColor Yellow
    Read-Host "按 Enter 关闭"
    exit 1
}

if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }

function Stop-Backend {
    & "$PSScriptRoot\kill_port.ps1" -Ports 8012
}

$null = [AppDomain]::CurrentDomain.add_ProcessExit({
    & "$PSScriptRoot\kill_port.ps1" -Ports 8012
})

$host.UI.RawUI.WindowTitle = "JNAO Backend :8012"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  JNAO Backend  http://127.0.0.1:8012" -ForegroundColor Cyan
Write-Host "  Ctrl+C 或关闭本窗口即停止" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Stop-Backend
Set-Location $backendDir

try {
    & $pythonExe -m uvicorn main:app --host 127.0.0.1 --port 8012 --reload
}
finally {
    Write-Host ""
    Write-Host "[CLEANUP] 正在停止后端..." -ForegroundColor Yellow
    Stop-Backend
    Write-Host "[DONE] 后端已停止" -ForegroundColor Green
    Start-Sleep -Seconds 1
}
