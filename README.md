# JNAO — 天赋成长平台

面向 K12 学生与家长的 AI 天赋成长综合平台，包含天赋测评、每日打卡、学科答疑、成长追踪四大核心模块。

## 四大模块

| 模块 | 说明 | 状态 |
|------|------|------|
| 🧭 天赋测试 | AI 驱动的天赋测评，35 题 → 雷达图报告 | ✅ 已实现 |
| 📅 今日训练 | 每日打卡训练，多技能并行 Tier 独立晋级（v2.0） | ✅ 已实现 |
| 💬 学科答疑 | AI 一对一辅导（数学/语文/英语），分科提示词 | ✅ 已实现 |
| 🏆 成长里程碑 | 时间线 + 徽章系统，追踪成长轨迹 | ✅ 已实现 |
| 👨‍👩‍👧 家长中心 | 家长注册登录 + 多孩子管理 | ✅ 已实现 |

## 技术栈

| 层 | 技术 | 端口 |
|---|---|---|
| 前端 | UniApp (Vue 3) | 5185 |
| 后端 | Python FastAPI + Uvicorn | 8012 |
| 数据库 | SQLite（单机开发）/ MySQL（共享开发/生产） | — |
| AI 对话 | 火山引擎豆包 (Doubao) | — |
| 测评 | 外部 JNAO API（m.jnao.com） | — |
| 语音 | 火山引擎 TTS / ASR | — |

## 项目结构

```
tianfu_daka/
├── backend/            # Python FastAPI 后端（端口 8012）
│   ├── app/api/        # API 路由（14 个模块）
│   ├── app/services/   # 业务逻辑层（45+ 个服务，v2.0 公式引擎+状态机+Tier晋级）
│   ├── app/agents/     # AI Agent 层（人设+路由+记忆）
│   ├── app/schemas/    # Pydantic 请求/响应模型
│   ├── app/db/         # 数据库模型 + 迁移
│   ├── config/         # YAML 配置（课程 / 进阶规则）
│   └── tests/          # 后端测试（pytest，32 文件）
├── vue_fronted/        # UniApp Vue 前端
│   ├── src/pages/      # 页面（training / talent / qa / growth / report / login / parent）
│   └── tests/          # 前端测试（vitest，3 文件 89 用例）
├── docs/               # 项目文档
├── scripts/            # 启动/停止脚本
├── tests/              # 发烟测试 + 集成测试
└── logs/               # 运行日志
```

## 快速开始

### 环境准备

```bash
# 后端
python -m venv .venv
source .venv/Scripts/activate   # Windows
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env   # 编辑填入 API Key
```

### 启动

**一键启动：**

| 系统 | 方式 |
|---|---|
| Windows | 双击 `scripts/start_all.bat` |
| Mac/Linux | `bash scripts/start_all.sh` |

**分别启动：**

```bash
# 后端 → http://127.0.0.1:8012
cd backend && python main.py

# 前端 → http://127.0.0.1:5185
cd vue_fronted && npm run dev
```

### 运行测试

```bash
# 后端全量
python -m pytest backend/tests/ -v

# 前端全量
cd vue_fronted && npm test

# 快速发烟（小改动验证，<2秒）
python -m pytest tests/smoke_test.py -v --tb=short
```

## 环境变量

后端需配置 `backend/.env`（不提交 Git）：

| 变量 | 说明 |
|---|---|
| `DOUBAO_API_KEY` | 火山引擎豆包 API 密钥 |
| `DOUBAO_API_BASE` | API 地址 |
| `DOUBAO_CHAT_MODEL` | 模型名称 |
| `DATABASE_URL` | 数据库连接（默认 SQLite） |
| `OSS_*` | 阿里云 OSS 音频存储配置 |

详见 `backend/.env.example`

## 文档

| 文档 | 说明 |
|------|------|
| **[体系架构设计](docs/体系架构设计.md)** | 训练系统架构全景 v2.0：状态机 + 公式引擎 + 规则引擎 |
| **[产品规格](docs/产品规格.md)** | 产品定位 + 四大模块 + 技术栈 v2.1 |
| **[项目结构说明](docs/项目结构说明.md)** | 目录结构 + 文件说明 |
| **[标准流程理解文档](docs/标准流程理解文档.md)** | 老板口述标准流程梳理与确认记录 |
| **[后端改造方案](docs/后端改造方案.md)** | v2.0 后端改造方案与实施顺序 |
| **[数据闭环与预留说明](docs/数据闭环与预留说明.md)** | AI 闭环实现 / 预留字段 / 明确不做项 |
| **[前端后端API文档](docs/前端后端API文档.md)** | 按页面编排的 API + 后端逻辑说明 |
| **[天赋测试](docs/功能模块文档/天赋测试.md)** | 6 阶段状态机 + API |
| **[今日训练](docs/功能模块文档/今日训练.md)** | 打卡模块设计 v2.0 |
| **[学科答疑](docs/功能模块文档/学科答疑.md)** | 分科 AI 辅导设计 |
| **[脑力奥秘音频资源](docs/data/脑力奥秘-音频资源说明.md)** | 41 条 MP3 音频清单 |
