#!/usr/bin/env bash
# 每 15 分钟增量同步 wx_member_snapshot（B）
#
# ⚠️ 当前暂停：微信一键登录数据暂不更新，请勿配置宝塔计划任务。
# 恢复同步后再启用。

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/sync_wx_snapshot_incremental.log"

mkdir -p "$LOG_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "[$(date '+%F %T')] ERROR: 缺少 $ENV_FILE" >> "$LOG_FILE"
  exit 1
fi

{
  echo "[$(date '+%F %T')] 开始增量同步 wx_member_snapshot ..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
    python tools/sync_wx_member_snapshot.py --incremental
  echo "[$(date '+%F %T')] 增量同步完成"
} >> "$LOG_FILE" 2>&1
