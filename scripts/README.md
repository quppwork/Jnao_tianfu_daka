# Scripts

## 推荐：一键启动

| 系统 | 方式 |
|------|------|
| **Windows** | 双击 `start_all.bat`，Ctrl+C 停止 |
| **Linux/Mac** | `bash start_all.sh`，Ctrl+C 停止 |

两个服务在**同一个终端**运行：
- 后端后台运行，日志输出到 `logs/backend.log`
- 前端前台运行
- Ctrl+C 停止时会自动清理后端进程

## 单独启动

| 脚本 | 说明 |
|------|------|
| `start_backend.bat` / `.sh` | 仅后端 → http://127.0.0.1:8011 |
| `start_frontend.bat` / `.sh` | 仅前端 → http://127.0.0.1:5185 |

启动前会自动清理端口占用。
