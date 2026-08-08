#!/usr/bin/env bash
# 截断过大的计划任务日志，避免 logs/ 无限增长
#
# 宝塔计划任务:
#   周期: 每周日 04:00
#   脚本: /bin/bash /www/wwwroot/jnao_daka/scripts/cron/cleanup_logs.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/cleanup_logs.log"
MAX_SIZE="${CRON_LOG_MAX_SIZE:-10M}"

mkdir -p "$LOG_DIR"

{
  echo "[$(date '+%F %T')] 开始清理 cron 日志 (max=$MAX_SIZE) ..."
  count=0
  if [ -d "$LOG_DIR" ]; then
    while IFS= read -r -d '' f; do
      echo "  truncate: $f"
      : > "$f"
      count=$((count + 1))
    done < <(find "$LOG_DIR" -maxdepth 1 -name '*.log' ! -name 'cleanup_logs.log' -size +"$MAX_SIZE" -print0 2>/dev/null || true)
  fi
  echo "[$(date '+%F %T')] 完成，截断 $count 个文件"
} >> "$LOG_FILE" 2>&1
