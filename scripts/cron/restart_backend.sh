#!/usr/bin/env bash
# 低峰重启 backend，释放进程内缓存累积（可选）
#
# 宝塔计划任务:
#   周期: 每周日 04:20
#   脚本: /bin/bash /www/wwwroot/jnao_daka/scripts/cron/restart_backend.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/restart_backend.log"

mkdir -p "$LOG_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "[$(date '+%F %T')] ERROR: 缺少 $ENV_FILE" >> "$LOG_FILE"
  exit 1
fi

{
  echo "[$(date '+%F %T')] 重启 backend ..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart backend
  sleep 5
  curl -sf "http://127.0.0.1:${FRONTEND_HOST_PORT:-5185}/api/ping" | head -c 200 || true
  echo
  echo "[$(date '+%F %T')] backend 重启完成"
} >> "$LOG_FILE" 2>&1
