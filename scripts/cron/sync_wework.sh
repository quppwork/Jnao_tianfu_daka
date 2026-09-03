#!/usr/bin/env bash
# 企业微信近 N 天收款 + 客户关联写库
#
# 宝塔计划任务示例:
#   任务类型: Shell
#   执行周期: 每小时（或每 30 分钟）
#   脚本: /bin/bash /www/wwwroot/jnao_daka/scripts/cron/sync_wework.sh
#
# 不要只靠 --skip-served：缓存丢失时脚本会自动改拉 contact_list。
# 缓存写在容器卷 /app/data/qywx_export（docker volume backend_data）。

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/sync_wework.log"

mkdir -p "$LOG_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "[$(date '+%F %T')] ERROR: 缺少 $ENV_FILE" >> "$LOG_FILE"
  exit 1
fi

{
  echo "[$(date '+%F %T')] 开始企微同步 ..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
    python -u tools/wework/sync_wework_pipeline.py --recent-only --apply --skip-detail --skip-served
  echo "[$(date '+%F %T')] 企微同步完成"
} >> "$LOG_FILE" 2>&1
