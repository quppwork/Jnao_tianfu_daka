# Scripts

## 推荐：一键启动（仓库根目录）

| 系统 | 方式 |
|------|------|
| **Windows** | 双击根目录 `start.bat`（内部调 `scripts\start_all.ps1`）；或 `scripts\start_all.bat` |
| **Linux/Mac** | `bash scripts/start_all.sh` |

**不要**再维护第二套「一键启停」逻辑：根目录 `start.bat` / `stop.bat` / `reset.bat` 只做转发；
真实流程集中在 `scripts/start_all.ps1`、`stop_all.ps1`、`run_backend.ps1`、`run_frontend.ps1`。

- 后端 → http://127.0.0.1:8012
- 前端 → http://127.0.0.1:5185

## 单独启动

| 脚本 | 说明 |
|------|------|
| `start_backend.bat` / `.sh` | 仅后端 |
| `start_frontend.bat` / `.sh` | 仅前端 |

启动前会尽量清理端口占用。运维脚本分类见 `backend/tools/README.md`。

## 线上日志（Loki + Grafana）

后端只打 **stdout**；`docker-compose.logging.yml` 用 **Alloy** 采集 Docker 日志写入 **Loki**，用 **Grafana** 实时查看与检索历史（默认保留约 14 天）。

部署（`deploy-baota.sh` 会自动叠加 logging compose）：

```bash
bash scripts/deploy-baota.sh
# 等价于:
# docker compose -f docker-compose.prod.yml -f docker-compose.logging.yml --env-file .env.production up -d
```

打开：`http://127.0.0.1:3000`（或宝塔反代）→ **Explore** → 数据源 Loki。

常用 LogQL：

```text
{container="jnao-daka-backend"}
{container="jnao-daka-backend"} |= "biz action="
{container="jnao-daka-backend"} |= "uid=42"
{container="jnao-daka-backend"} |~ "(?i)error"
```

业务日志字段示例：

```text
biz action=training.checkin uid=42 role=student rid=a1b2c3d4 result=ok ms=128 plan_id=9
```

`.env.production` 需配置 `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`（见 `.env.production.example`）。