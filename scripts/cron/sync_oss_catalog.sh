#!/usr/bin/env bash
# 每日同步 OSS 媒体目录 → content_item（音频 JSON + 视频 shipin/）
#
# 宝塔计划任务示例:
#   任务类型: Shell
#   执行周期: 每天 03:30
#   脚本: /bin/bash /www/wwwroot/jnao_daka/scripts/cron/sync_oss_catalog.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/sync_oss_catalog.log"

mkdir -p "$LOG_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "[$(date '+%F %T')] ERROR: 缺少 $ENV_FILE" >> "$LOG_FILE"
  exit 1
fi

{
  echo "[$(date '+%F %T')] 开始同步 OSS 媒体目录 ..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
    python tools/sync_oss_media.py --scan-shipin
  echo "[$(date '+%F %T')] OSS 媒体同步完成"
} >> "$LOG_FILE" 2>&1
