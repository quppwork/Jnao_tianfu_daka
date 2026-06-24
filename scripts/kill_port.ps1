param(
    [Parameter(Mandatory = $true)]
    [int[]]$Ports
)

$ErrorActionPreference = "SilentlyContinue"

foreach ($port in $Ports) {
    $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $listeners) { continue }

    foreach ($procId in ($listeners | Select-Object -ExpandProperty OwningProcess -Unique)) {
        if ($procId -le 4) { continue }
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  Kill port $port -> PID $procId ($($proc.ProcessName))" -ForegroundColor Gray
            taskkill /F /T /PID $procId | Out-Null
        }
    }
}
