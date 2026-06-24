$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $root "vue_fronted"

if (-not (Test-Path (Join-Path $frontendDir "package.json"))) {
    Write-Host "[ERROR] 未找到前端目录: $frontendDir" -ForegroundColor Red
    Read-Host "按 Enter 关闭"
    exit 1
}

function Stop-Frontend {
    & "$PSScriptRoot\kill_port.ps1" -Ports 5185
}

$null = [AppDomain]::CurrentDomain.add_ProcessExit({
    & "$PSScriptRoot\kill_port.ps1" -Ports 5185
})

$host.UI.RawUI.WindowTitle = "JNAO Frontend :5185"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  JNAO Frontend  http://127.0.0.1:5185" -ForegroundColor Cyan
Write-Host "  Ctrl+C 或关闭本窗口即停止" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Stop-Frontend
Set-Location $frontendDir

try {
    npm run dev
}
finally {
    Write-Host ""
    Write-Host "[CLEANUP] 正在停止前端..." -ForegroundColor Yellow
    Stop-Frontend
    Write-Host "[DONE] 前端已停止" -ForegroundColor Green
    Start-Sleep -Seconds 1
}
