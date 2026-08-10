#!/usr/bin/env bash
# 归档超期 QA / Guide 聊天会话（默认保留 180 天）
#
# 宝塔计划任务:
#   周期: 每月 1 日 04:15
#   脚本: /bin/bash /www/wwwroot/jnao_daka/scripts/cron/archive_chat_history.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/archive_chat_history.log"
RETAIN_DAYS="${CHAT_ARCHIVE_RETAIN_DAYS:-180}"
QA_KEEP_RECENT="${CHAT_ARCHIVE_QA_KEEP_RECENT:-20}"
GUIDE_KEEP_RECENT="${CHAT_ARCHIVE_GUIDE_KEEP_RECENT:-10}"
BATCH_SIZE="${CHAT_ARCHIVE_BATCH_SIZE:-100}"

mkdir -p "$LOG_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "[$(date '+%F %T')] ERROR: 缺少 $ENV_FILE" >> "$LOG_FILE"
  exit 1
fi

{
  echo "[$(date '+%F %T')] 开始归档聊天历史 (retain=${RETAIN_DAYS}d qa_keep=${QA_KEEP_RECENT} guide_keep=${GUIDE_KEEP_RECENT}) ..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
    python tools/archive_chat_history.py \
      --days "$RETAIN_DAYS" \
      --qa-keep-recent "$QA_KEEP_RECENT" \
      --guide-keep-recent "$GUIDE_KEEP_RECENT" \
      --batch-size "$BATCH_SIZE"
  echo "[$(date '+%F %T')] 聊天历史归档完成"
} >> "$LOG_FILE" 2>&1
