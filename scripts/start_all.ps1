$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  JNAO - 一键启动前后端" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "[CLEAN] 清理旧进程..." -ForegroundColor Gray
& "$PSScriptRoot\stop_all.ps1"

Write-Host "[START] 打开后端窗口 (8012)..." -ForegroundColor Yellow
Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $PSScriptRoot "run_backend.ps1")
) -WorkingDirectory $root

Write-Host "[WAIT] 等待后端就绪..." -ForegroundColor Gray
$ready = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $code = & curl.exe -s -o $null -w "%{http_code}" --max-time 1 "http://127.0.0.1:8012/api/ping" 2>$null
        if ($code -eq "200") {
            Write-Host "[BACKEND] Ready" -ForegroundColor Green
            $ready = $true
            break
        }
    } catch { }
}
if (-not $ready) {
    Write-Host "[WARN] 后端尚未响应，前端窗口仍会启动" -ForegroundColor DarkYellow
}

Write-Host "[START] 打开前端窗口 (5185)..." -ForegroundColor Yellow
Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $PSScriptRoot "run_frontend.ps1")
) -WorkingDirectory $root

Write-Host ""
Write-Host "  Backend:  http://127.0.0.1:8012" -ForegroundColor Green
Write-Host "  Frontend: http://127.0.0.1:5185" -ForegroundColor Green
Write-Host ""
Write-Host "  已弹出两个 PowerShell 窗口" -ForegroundColor Cyan
Write-Host "  关闭对应窗口即可停止该服务" -ForegroundColor Cyan
Write-Host "  或运行 scripts\stop_all.ps1 全部停止" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
