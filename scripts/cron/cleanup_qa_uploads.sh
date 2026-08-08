#!/usr/bin/env bash
# 清理过期学科答疑拍图（默认保留 30 天）
#
# 宝塔计划任务:
#   周期: 每周日 04:10
#   脚本: /bin/bash /www/wwwroot/jnao_daka/scripts/cron/cleanup_qa_uploads.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/cleanup_qa_uploads.log"
RETAIN_DAYS="${QA_UPLOAD_RETAIN_DAYS:-30}"

mkdir -p "$LOG_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "[$(date '+%F %T')] ERROR: 缺少 $ENV_FILE" >> "$LOG_FILE"
  exit 1
fi

{
  echo "[$(date '+%F %T')] 开始清理 QA 拍图 (retain=${RETAIN_DAYS}d) ..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
    python tools/cleanup_qa_uploads.py --days "$RETAIN_DAYS"
  echo "[$(date '+%F %T')] QA 拍图清理完成"
} >> "$LOG_FILE" 2>&1
