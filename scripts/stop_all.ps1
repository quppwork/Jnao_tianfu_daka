$ErrorActionPreference = "SilentlyContinue"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  JNAO - Stop All Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Kill by port
foreach ($port in @(8012, 5185)) {
    Write-Host "[PORT] Cleaning port $port..." -ForegroundColor Gray
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conns) {
        $pids = $conns.OwningProcess | Select-Object -Unique
        foreach ($pid in $pids) {
            if ($pid -gt 0) {
                $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
                if ($proc) {
                    Write-Host "  Kill PID $pid ($($proc.ProcessName))" -ForegroundColor Gray
                    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                }
            }
        }
    } else {
        Write-Host "  Port $port is free" -ForegroundColor Gray
    }
}

Write-Host "  All services stopped." -ForegroundColor Green
Write-Host ""
