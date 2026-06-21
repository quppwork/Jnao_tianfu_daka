# JNAO - Start All Services (PowerShell)
$ErrorActionPreference = "Continue"

Write-Host "========================================"
Write-Host "  JNAO - Start All Services"
Write-Host "========================================"
Write-Host "[START] $(Get-Date -Format 'HH:mm:ss')"
Write-Host ""

$root = $PSScriptRoot | Split-Path -Parent
Set-Location $root

# --- Kill stale processes ---
. "$PSScriptRoot\stop_all.ps1"

# --- Activate venv ---
$venvActivate = Join-Path $root ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
    Write-Host "[ERROR] .venv not found"
    Read-Host "Press Enter"
    exit 1
}
. $venvActivate

# --- Start backend via cmd (reliable background + redirect) ---
Write-Host "[TIME] backend start: $(Get-Date -Format 'HH:mm:ss')"
Write-Host "[INFO] Starting backend on http://127.0.0.1:8011"
$logsDir = Join-Path $root "logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
$backendLog = Join-Path $logsDir "backend.log"
$backendDir = Join-Path $root "backend"
$uvicornExe = Join-Path $root ".venv\Scripts\uvicorn.exe"

if (Test-Path $backendLog) { Remove-Item $backendLog -Force -ErrorAction SilentlyContinue }
cmd /c "cd /d `"$backendDir`" && start /B `"backend`" `"$uvicornExe`" main:app --host 127.0.0.1 --port 8011 --reload > `"$backendLog`" 2>&1"

# --- Wait for backend ---
Write-Host "[TIME] health poll start: $(Get-Date -Format 'HH:mm:ss')"
Write-Host "[INFO] Waiting for backend..."
$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    $httpCode = curl.exe -s -o NUL -w "%{http_code}" "http://127.0.0.1:8011/api/health" 2>$null
    if ($httpCode -eq "200") {
        $bkPid = (Get-NetTCPConnection -LocalPort 8011 -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
        if ($bkPid) {
            $bkPid | Out-File -FilePath (Join-Path $logsDir "backend.pid") -NoNewline
        }
        Write-Host "  [OK] Backend ready (PID $bkPid) at $(Get-Date -Format 'HH:mm:ss')"
        $ready = $true
        break
    }
}
if (-not $ready) {
    Write-Host "  [WARN] Backend not responding. Check logs\backend.log"
}

# --- Start frontend ---
Write-Host "[TIME] frontend start: $(Get-Date -Format 'HH:mm:ss')"
Write-Host "[INFO] Starting frontend on http://127.0.0.1:5185"
$frontendDir = Join-Path $root "h5_fronted"
Set-Location $frontendDir

Write-Host ""
Write-Host "  Backend:  http://127.0.0.1:8011"
Write-Host "  Frontend: http://127.0.0.1:5185"
Write-Host "  Ctrl+C to stop frontend"
Write-Host "========================================"
Write-Host ""

# Run vite (foreground)
try {
    npm run dev
} finally {
    Write-Host ""
    Write-Host "[INFO] Frontend stopped. Cleaning up..."
    Set-Location $root
    . "$PSScriptRoot\stop_all.ps1"
}
