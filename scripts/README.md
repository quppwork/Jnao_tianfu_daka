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

## 线上行为日志（按用户排查）

每条业务日志带 **uid**（`ChildUser.id`，全站唯一）和 **rid**（单次请求 ID）：

```text
biz action=training.checkin uid=42 role=student rid=a1b2c3d4 result=ok ms=128 plan_id=9
```

服务器查看：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f --tail=200 backend
# 或按人过滤：
docker compose -f docker-compose.prod.yml --env-file .env.production logs backend 2>&1 | grep 'uid=42'
docker compose -f docker-compose.prod.yml --env-file .env.production logs backend 2>&1 | grep 'biz action='
```
