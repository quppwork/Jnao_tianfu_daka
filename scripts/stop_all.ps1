# JNAO - Stop All Services (PowerShell)
$ErrorActionPreference = "SilentlyContinue"

Write-Host "========================================"
Write-Host "  JNAO - Stop All Services"
Write-Host "========================================"
Write-Host ""

$root = Split-Path -Parent $PSScriptRoot

# Kill by PID file
$pidFile = Join-Path $root "logs\backend.pid"
if (Test-Path $pidFile) {
    $bkPid = Get-Content $pidFile -Raw
    if ($bkPid -match '\d+') {
        Write-Host "[INFO] Stopping backend PID $bkPid..."
        Stop-Process -Id ([int]$bkPid) -Force
        Remove-Item $pidFile -Force
        Write-Host "  [OK] Backend stopped"
    }
} else {
    Write-Host "  [WARN] No PID file for backend"
}

# Clean port 8011
Write-Host "[INFO] Cleaning port 8011..."
. "$PSScriptRoot\kill_port.ps1" -Port 8011

# Clean port 5185
Write-Host "[INFO] Cleaning port 5185..."
. "$PSScriptRoot\kill_port.ps1" -Port 5185

Write-Host ""
Write-Host "  All services stopped."
Write-Host ""
