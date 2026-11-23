$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
& "$root\.venv\Scripts\python.exe" "$PSScriptRoot\reset_local_data.py"
