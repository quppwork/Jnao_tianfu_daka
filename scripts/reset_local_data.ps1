$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
& "$root\.venv\Scripts\python.exe" "$PSScriptRoot\reset_local_data.py"
Write-Host ""
Write-Host "浏览器：打开 http://localhost:5185 按 F12，在 Console 粘贴：" -ForegroundColor Yellow
Write-Host "  localStorage.clear(); location.reload()" -ForegroundColor Cyan
