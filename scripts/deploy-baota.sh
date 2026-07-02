#!/usr/bin/env bash
# 宝塔阿里云一键部署脚本（在服务器上执行）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"

echo "========================================"
echo "  JNAO 宝塔生产部署"
echo "========================================"

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] 未安装 Docker，请先在宝塔「软件商店」安装 Docker 管理器"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "[ERROR] 未找到 docker compose，请升级 Docker 或安装 compose 插件"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  if [ -f ".env.production.example" ]; then
    cp .env.production.example "$ENV_FILE"
    echo "[WARN] 已生成 $ENV_FILE，请先编辑数据库、域名、API Key 后再执行本脚本"
    exit 1
  fi
  echo "[ERROR] 缺少 $ENV_FILE"
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "$ENV_FILE"
set +a

if [ -z "${DOUBAO_API_KEY:-}" ] || [ "$DOUBAO_API_KEY" = "your-ark-api-key" ]; then
  echo "[ERROR] 请在 $ENV_FILE 中配置 DOUBAO_API_KEY"
  exit 1
fi

if [ -z "${SITE_DOMAIN:-}" ] || [ "$SITE_DOMAIN" = "https://your-domain.com" ]; then
  echo "[ERROR] 请在 $ENV_FILE 中配置 SITE_DOMAIN（如 https://jnaosoft.cn）"
  exit 1
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "[ERROR] 请在 $ENV_FILE 中配置 DATABASE_URL（阿里云 RDS）"
  exit 1
fi

echo "[1/4] 构建镜像（生产精简依赖，无 pytest/ffmpeg/whisper）..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build

echo "[2/4] 启动容器..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

echo "[3/4] 等待后端健康检查..."
sleep 5
docker compose -f "$COMPOSE_FILE" ps

echo "[4/4] 表结构由后端 init_db 自动创建/补丁（migrate.py）"
echo "      若库中已有 v1 训练进度数据，可选手动执行一次："
echo "      docker compose -f $COMPOSE_FILE exec backend python migrate_state_v2.py"

FRONTEND_PORT="${FRONTEND_HOST_PORT:-5185}"
echo ""
echo "========================================"
echo "  部署完成"
echo "========================================"
echo "  本机访问: http://127.0.0.1:${FRONTEND_PORT}"
echo ""
echo "  宝塔后续:"
echo "  1. 网站 → 反向代理 → http://127.0.0.1:${FRONTEND_PORT}"
echo "  2. SSL → 申请证书"
echo "  3. 安全组仅开放 22/80/443"
echo ""
echo "  常用命令:"
echo "    日志: docker compose -f $COMPOSE_FILE logs -f backend"
echo "    重启: docker compose -f $COMPOSE_FILE restart"
