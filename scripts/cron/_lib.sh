# shellcheck shell=bash
# 宝塔 cron 脚本共用变量（source 引入，勿直接执行）

cron_project_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd
}

cron_log_dir() {
  echo "$(cron_project_root)/logs"
}

cron_compose_file() {
  echo "docker-compose.prod.yml"
}

cron_env_file() {
  echo ".env.production"
}
