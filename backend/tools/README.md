# backend/tools

运维/一次性脚本（**不是**应用运行时依赖）。按目录分类：

| 目录 | 用途 |
|------|------|
| `wework/` | 企业微信客户/收款/标签同步与导出 |
| `cleanup/` | 数据清理、压测痕迹、会话归档、重置非管理员 |
| `ops/` | OSS/短信/百炼抽检、恢复家长、压测种子、媒体导出 |

根目录下同名 `.py` 为**兼容 shim**（转发到子目录），新用法请直接：

```bash
cd backend
python tools/wework/sync_wework_pipeline.py
python tools/cleanup/wipe_users_for_retest.py
python tools/ops/kb_qa_smoke.py
```

含密码的 `*loadtest*.csv` 已在 `.gitignore`，勿提交。
