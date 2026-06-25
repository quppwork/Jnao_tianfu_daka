# 数据库定时备份 — MySQL jnao_daka
# 用法: powershell -ExecutionPolicy Bypass -File scripts\backup_db.ps1
# 定时: 任务计划程序每日运行 backup.bat

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root "backend\.env"
$backupDir = Join-Path $root "backups"
$keepDays = 30

if (-not (Test-Path $envFile)) {
    Write-Host "[ERROR] 未找到 backend\.env" -ForegroundColor Red
    exit 1
}

$dbUrl = $null
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*DATABASE_URL=(.+)$') {
        $dbUrl = $matches[1].Trim()
    }
}

if (-not $dbUrl -or $dbUrl -notmatch '^mysql') {
    Write-Host "[SKIP] 非 MySQL 环境，跳过 mysqldump（SQLite 请直接复制 backend\data\*.db）" -ForegroundColor Yellow
    exit 0
}

if ($dbUrl -match 'mysql\+pymysql://([^:]+):([^@]+)@([^:/]+):?(\d+)?/(\w+)') {
    $user = $matches[1]
    $pass = $matches[2]
    $dbHost = $matches[3]
    $port = if ($matches[4]) { $matches[4] } else { "3306" }
    $db = $matches[5]
} else {
    Write-Host "[ERROR] 无法解析 DATABASE_URL" -ForegroundColor Red
    exit 1
}

$mysqldump = Get-Command mysqldump -ErrorAction SilentlyContinue
if (-not $mysqldump) {
    Write-Host "[ERROR] 未找到 mysqldump，请安装 MySQL 客户端并加入 PATH" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outFile = Join-Path $backupDir "jnao_daka_$stamp.sql"

Write-Host "[BACKUP] $db -> $outFile" -ForegroundColor Cyan
$env:MYSQL_PWD = $pass
& mysqldump -h $dbHost -P $port -u $user --single-transaction --routines --triggers $db | Out-File -FilePath $outFile -Encoding utf8
Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] mysqldump 失败" -ForegroundColor Red
    exit 1
}

$sizeMb = [math]::Round((Get-Item $outFile).Length / 1MB, 2)
Write-Host "[OK] 备份完成 ${sizeMb} MB" -ForegroundColor Green

Get-ChildItem $backupDir -Filter "jnao_daka_*.sql" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$keepDays) } |
    ForEach-Object {
        Write-Host "[CLEAN] 删除过期备份 $($_.Name)" -ForegroundColor Gray
        Remove-Item $_.FullName -Force
    }
