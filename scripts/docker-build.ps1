# 构建本地 Docker 镜像
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "========================================"
Write-Host "  JNAO - Build Docker Images"
Write-Host "========================================"

docker compose build

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker build failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[OK] Images built:"
docker images --format "  {{.Repository}}:{{.Tag}}" | Select-String "jnao-daka"
Write-Host ""
Write-Host "Start:  docker compose up -d"
Write-Host "Stop:   docker compose down"
Write-Host "Logs:   docker compose logs -f"
