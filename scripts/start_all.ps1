$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  JNAO - Start All Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# --- Stop stale ---
Write-Host "[CLEAN] Stopping old processes..." -ForegroundColor Gray
& "$PSScriptRoot\stop_all.ps1"

# --- Start Backend (hidden window) ---
Write-Host "[BACKEND] Starting on port 8011..." -ForegroundColor Yellow
$backendDir = Join-Path $root "backend"
$logsDir = Join-Path $root "logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
$logFile = Join-Path $logsDir "backend.log"

$backendProc = Start-Process -FilePath "powershell" `
  -ArgumentList "-Command", "& { `$host.UI.RawUI.WindowTitle='JNAO-Backend'; python -m uvicorn main:app --host 127.0.0.1 --port 8011 --reload 2>&1 | Out-File '$logFile' }" `
  -WorkingDirectory $backendDir `
  -PassThru `
  -WindowStyle Minimized

# Save PID
$backendProc.Id | Out-File (Join-Path $logsDir "backend.pid") -NoNewline

# --- Wait for backend ---
Write-Host "[BACKEND] Waiting for health check..." -ForegroundColor Gray
$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8011/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) {
            Write-Host "[BACKEND] Ready (PID $($backendProc.Id))" -ForegroundColor Green
            $ready = $true
            break
        }
    } catch { }
}
if (-not $ready) {
    Write-Host "[WARN] Backend not responding yet" -ForegroundColor DarkYellow
}

# --- Start Frontend (foreground) ---
Write-Host "[FRONTEND] Starting on port 5185..." -ForegroundColor Yellow
$frontendDir = Join-Path $root "vue_fronted"

Write-Host ""
Write-Host "  Backend:  http://127.0.0.1:8011" -ForegroundColor Green
Write-Host "  Frontend: http://127.0.0.1:5185" -ForegroundColor Green
Write-Host "  Press Ctrl+C to stop all" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

try {
    Set-Location $frontendDir
    npm run dev
} finally {
    Write-Host ""
    Write-Host "[CLEANUP] Stopping all services..." -ForegroundColor Yellow
    & "$PSScriptRoot\stop_all.ps1"
    Write-Host "[DONE] All services stopped." -ForegroundColor Green
}
