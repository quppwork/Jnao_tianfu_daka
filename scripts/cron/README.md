# 宝塔计划任务（生产环境）

项目路径以 **`/www/wwwroot/jnao_daka`** 为例；按实际部署目录替换。

## 前置条件

1. 已 `git pull` 且 `docker compose -f docker-compose.prod.yml --env-file .env.production up -d`
2. `.env.production` 已配置 `REDIS_URL`、`DATABASE_URL`、`OSS_*` 等
3. 脚本可执行（首次部署后执行一次）：

```bash
chmod +x /www/wwwroot/jnao_daka/scripts/cron/*.sh
mkdir -p /www/wwwroot/jnao_daka/logs
```

---

## 需要配置的任务（当前推荐）

| # | 任务名称 | 周期 | 执行脚本 |
|---|----------|------|----------|
| 1 | OSS 媒体同步 | 每天 **03:30** | `/bin/bash /www/wwwroot/jnao_daka/scripts/cron/sync_oss_catalog.sh` |
| 2 | Cron 日志截断 | 每周日 **04:00** | `/bin/bash /www/wwwroot/jnao_daka/scripts/cron/cleanup_logs.sh` |
| 3 | QA 拍图清理 | 每周日 **04:10** | `/bin/bash /www/wwwroot/jnao_daka/scripts/cron/cleanup_qa_uploads.sh` |
| 4 | Backend 重启（可选） | 每周日 **04:20** | `/bin/bash /www/wwwroot/jnao_daka/scripts/cron/restart_backend.sh` |

### 暂不配置（微信一键登录数据暂停更新）

| 脚本 | 说明 |
|------|------|
| `sync_wx_snapshot_incremental.sh` | 微信会员增量同步，**勿配** |
| `sync_wx_snapshot_daily.sh` | 微信会员全量同步，**勿配** |

---

## 宝塔面板操作步骤

### 1. 进入计划任务

**宝塔面板 → 计划任务 → 添加任务**

### 2. 添加「OSS 媒体同步」（必配）

- **任务类型**：Shell 脚本
- **任务名称**：JNAO OSS 媒体同步
- **执行周期**：每天
- **执行时间**：03:30
- **脚本内容**：

```bash
/bin/bash /www/wwwroot/jnao_daka/scripts/cron/sync_oss_catalog.sh
```

### 3. 添加「Cron 日志截断」

- **任务类型**：Shell 脚本
- **任务名称**：JNAO 清理计划任务日志
- **执行周期**：每周 → 星期日 → 04:00
- **脚本内容**：

```bash
/bin/bash /www/wwwroot/jnao_daka/scripts/cron/cleanup_logs.sh
```

### 4. 添加「QA 拍图清理」

- **任务类型**：Shell 脚本
- **任务名称**：JNAO 清理答疑拍图
- **执行周期**：每周 → 星期日 → 04:10
- **脚本内容**：

```bash
/bin/bash /www/wwwroot/jnao_daka/scripts/cron/cleanup_qa_uploads.sh
```

保留天数可在 `.env.production` 增加（可选）：

```env
QA_UPLOAD_RETAIN_DAYS=30
```

### 5. 添加「Backend 重启」（可选）

- **任务类型**：Shell 脚本
- **任务名称**：JNAO 低峰重启 Backend
- **执行周期**：每周 → 星期日 → 04:20
- **脚本内容**：

```bash
/bin/bash /www/wwwroot/jnao_daka/scripts/cron/restart_backend.sh
```

---

## 日志位置

| 任务 | 日志文件 |
|------|----------|
| OSS 同步 | `logs/sync_oss_catalog.log` |
| 日志截断 | `logs/cleanup_logs.log` |
| QA 拍图 | `logs/cleanup_qa_uploads.log` |
| Backend 重启 | `logs/restart_backend.log` |

查看示例：

```bash
tail -30 /www/wwwroot/jnao_daka/logs/sync_oss_catalog.log
```

---

## 手动验证（SSH）

```bash
cd /www/wwwroot/jnao_daka

# OSS 同步
/bin/bash scripts/cron/sync_oss_catalog.sh

# QA 拍图（预览）
docker compose -f docker-compose.prod.yml --env-file .env.production exec -T backend \
  python tools/cleanup_qa_uploads.py --dry-run

# OSS 可读性
docker compose -f docker-compose.prod.yml --env-file .env.production exec -T backend \
  python tools/check_oss_read.py
```

---

## 说明

- **Redis 缓存**：API 读缓存带 TTL，**无需**单独清理 cron。
- **OSS 播放 token**：走 backend 流代理，**无需**刷新 token 任务。
- 恢复微信登录数据同步后，再启用 `sync_wx_snapshot_*.sh` 并参考脚本内注释配置周期。
