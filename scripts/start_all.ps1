$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  JNAO - 启动本地 API" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "[CLEAN] 清理旧进程..." -ForegroundColor Gray
& "$PSScriptRoot\stop_all.ps1"

# 优先 PowerShell 7，没有再回退 Windows PowerShell 5.1
$shellExe = $null
foreach ($cand in @(
    (Get-Command pwsh -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
    "$env:LOCALAPPDATA\Microsoft\WindowsApps\pwsh.exe",
    "$env:ProgramFiles\PowerShell\7\pwsh.exe",
    "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"
)) {
    if ($cand -and (Test-Path $cand)) { $shellExe = $cand; break }
}
if (-not $shellExe) { $shellExe = "powershell.exe" }

Write-Host "[START] 打开后端窗口 (8012) via $([IO.Path]::GetFileName($shellExe))..." -ForegroundColor Yellow
Start-Process $shellExe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $PSScriptRoot "run_backend.ps1")
) -WorkingDirectory $root

Write-Host "[WAIT] 等待后端就绪..." -ForegroundColor Gray
$ready = $false
# uvicorn --reload 冷启动常见 >7s；过短会导致误报 WARN
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $code = & curl.exe -s -o $null -w "%{http_code}" --max-time 1 "http://127.0.0.1:8012/api/ping" 2>$null
        if ($code -eq "200") {
            Write-Host "[BACKEND] Ready ($([math]::Round(($i+1)*0.5,1))s)" -ForegroundColor Green
            $ready = $true
            break
        }
    } catch { }
}
if (-not $ready) {
    Write-Host "[WARN] 后端 20s 内未响应，请查看 Backend 窗口" -ForegroundColor DarkYellow
}

Write-Host ""
Write-Host "  API  http://127.0.0.1:8012" -ForegroundColor Green
Write-Host "  在 HBuilderX 打开 frontend 运行客户端" -ForegroundColor Cyan
Write-Host "  关闭 Backend 窗口或运行 scripts\stop_all.ps1 停止 API" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
