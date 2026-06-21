# 清理占用指定端口的进程（含子进程树）
# 用法: powershell -File kill_port.ps1 8011
param(
    [int]$Port = 8011
)

$connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if (-not $connections) {
    Write-Host "  [OK] Port $Port is free"
    exit 0
}

$processIds = $connections | ForEach-Object { $_.OwningProcess } | Where-Object { $_ -gt 0 } | Select-Object -Unique
if (-not $processIds) {
    Write-Host "  [OK] Port $Port is free (stale entries)"
    exit 0
}

foreach ($procId in $processIds) {
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($proc) {
        $name = $proc.ProcessName
        Write-Host "  [KILL] PID $procId ($name) on port $Port — killing tree"
        # Kill children first, then parent
        $children = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $procId }
        foreach ($child in $children) {
            $childProc = Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
            if ($childProc) {
                Write-Host "    [KILL] Child PID $($child.ProcessId) ($($childProc.ProcessName))"
                Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue
            }
        }
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Seconds 1
Write-Host "  [OK] Port $Port cleared"
