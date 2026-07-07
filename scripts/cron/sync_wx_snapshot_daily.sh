#!/usr/bin/env bash
# 每天凌晨 4:00 从老库拉取 ys_wx_member → jnao_daka.wx_member_snapshot
#
# 宝塔「计划任务」示例:
#   任务类型: Shell
#   执行周期: 每天 04:00
#   脚本: /bin/bash /www/wwwroot/jnao_daka/scripts/cron/sync_wx_snapshot_daily.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/sync_wx_snapshot.log"

mkdir -p "$LOG_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "[$(date '+%F %T')] ERROR: 缺少 $ENV_FILE" >> "$LOG_FILE"
  exit 1
fi

{
  echo "[$(date '+%F %T')] 开始同步 wx_member_snapshot ..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
    python tools/sync_wx_member_snapshot.py
  echo "[$(date '+%F %T')] 同步完成"
} >> "$LOG_FILE" 2>&1
