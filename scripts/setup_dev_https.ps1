# 为局域网手机调试生成受信任的 HTTPS 证书（需 mkcert）
# 用法：在项目根目录 PowerShell 执行  .\scripts\setup_dev_https.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$certDir = Join-Path $root "vue_fronted\.cert"
$certFile = Join-Path $certDir "cert.pem"
$keyFile = Join-Path $certDir "key.pem"

function Get-LanIp {
    $ip = Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -notmatch '^127\.' -and $_.PrefixOrigin -ne 'WellKnown' } |
        Select-Object -First 1 -ExpandProperty IPAddress
    if (-not $ip) { $ip = "127.0.0.1" }
    return $ip
}

function Ensure-Mkcert {
    $mk = Get-Command mkcert -ErrorAction SilentlyContinue
    if ($mk) { return $mk.Source }
    Write-Host "[INFO] 正在安装 mkcert（一次性）..." -ForegroundColor Yellow
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        winget install -e --id FiloSottile.mkcert --accept-package-agreements --accept-source-agreements
    } else {
        Write-Host "[ERROR] 未找到 winget。请手动安装 mkcert: https://github.com/FiloSottile/mkcert" -ForegroundColor Red
        exit 1
    }
    $mk = Get-Command mkcert -ErrorAction SilentlyContinue
    if (-not $mk) {
        Write-Host "[ERROR] mkcert 安装后请重新打开终端再运行本脚本" -ForegroundColor Red
        exit 1
    }
    return $mk.Source
}

$lanIp = Get-LanIp
$mkcertPath = Ensure-Mkcert

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  JNAO 开发 HTTPS 证书" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "局域网 IP: $lanIp" -ForegroundColor Gray
Write-Host ""

& $mkcertPath -install
New-Item -ItemType Directory -Force -Path $certDir | Out-Null
& $mkcertPath -cert-file $certFile -key-file $keyFile localhost 127.0.0.1 $lanIp ::1

Write-Host ""
Write-Host "[OK] 证书已生成: $certDir" -ForegroundColor Green
Write-Host ""
Write-Host "下一步：" -ForegroundColor Yellow
Write-Host "  1. 重启前端: cd vue_fronted; npm run dev"
Write-Host "  2. 手机浏览器打开: https://${lanIp}:5185"
Write-Host ""
Write-Host "iPhone 首次还需（一次性）：" -ForegroundColor Yellow
Write-Host "  - 用 Safari 打开上述地址，按提示安装描述文件"
Write-Host "  - 设置 → 通用 → 关于本机 → 证书信任设置 → 开启 mkcert 根证书"
Write-Host ""
Write-Host "Android：" -ForegroundColor Yellow
Write-Host "  - 将电脑上的 mkcert 根证书传到手机并安装为「用户证书」"
Write-Host "  - 根证书路径通常在: $env:LOCALAPPDATA\mkcert\rootCA.pem"
Write-Host ""
