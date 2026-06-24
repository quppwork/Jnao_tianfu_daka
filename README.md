# JNAO — 天赋成长平台

面向 K12 学生与家长的 AI 天赋成长综合平台，包含天赋测评、每日打卡、学科答疑、成长追踪四大核心模块。

## 四大模块

| 模块 | 说明 | 状态 |
|------|------|------|
| 🧭 天赋测试 | AI 驱动的天赋测评，35 题 → 雷达图报告 | ✅ 已实现 |
| 📅 今日训练 | 每日打卡训练，视频+音频，顺序解锁 | 🔨 设计中 |
| 💬 学科答疑 | AI 一对一辅导（数学/语文/英语/科学） | 🔒 待开发 |
| 🏆 成长里程碑 | 时间线 + 徽章系统，追踪成长轨迹 | 🔒 待开发 |

## 技术栈

| 层 | 技术 | 端口 |
|---|---|---|
| 前端 | UniApp (Vue 3) [计划] / React (H5 旧版) | 5185 |
| 后端 | Python FastAPI + Uvicorn | 8011 |
| 数据库 | MySQL（开发共用 3306） | 3306 |
| AI 对话 | 上游 tianfu_rag 代理 | 8010 |
| 测评 | 外部 JNAO API（m.jnao.com） | — |

## 项目结构

```
tianfu_daka/
├── backend/            # Python FastAPI 后端
├── h5_fronted/         # React H5 前端（旧版，将替换）
├── vue_fronted/        # UniApp Vue 前端（新版）
│   ├── tests_fronted/  # 设计预览原型（v1/v2）
│   └── src/            # 正式 UniApp 代码（待开发）
├── docs/               # 项目文档
├── scripts/            # 启动/停止脚本
├── tests/              # 集成测试
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

# 前端（旧版 React）
cd h5_fronted && npm install
```

### 启动

**一键启动：**

| 系统 | 方式 |
|---|---|
| Windows | 双击 `scripts/start_all.bat` |
| Mac/Linux | `bash scripts/start_all.sh` |

**分别启动：**

```bash
# 后端 → http://127.0.0.1:8011
uvicorn backend.main:app --host 127.0.0.1 --port 8011 --reload

# 前端 → http://127.0.0.1:5185
cd h5_fronted && npm run dev
```

### 设计预览（给老板看的原型）

```bash
# 直接双击打开：
vue_fronted/tests_fronted/v1/index.html   # 浅色版
vue_fronted/tests_fronted/v2/index.html   # 暗黑版
```

### 运行测试

```bash
# 后端
pytest tests/ -v

# 前端
cd h5_fronted && npm test
```

## 环境变量

后端需配置 `backend/.env`（不提交 Git）：

| 变量 | 说明 |
|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `DEEPSEEK_API_BASE` | API 地址（默认 `https://api.deepseek.com`） |
| `DEEPSEEK_CHAT_MODEL` | 模型名称（默认 `deepseek-v4-flash`） |

## 文档

| 文档 | 说明 |
|------|------|
| **[从 0 到 1 实施手册（Cursor 协作）](docs/从0到1实施手册-Cursor协作版.md)** | MVP 分阶段任务清单，给 Cursor 按序开发 |
| **[老板确认清单（可填写）](docs/老板确认清单-可填写.md)** | 需老板确认的业务规则 |
| **[脑力奥秘音频资源说明](docs/data/脑力奥秘-音频资源说明.md)** | 五天赋 MP3 URL、标签、SQL |
| [brain_power_audio_catalog.json](docs/data/brain_power_audio_catalog.json) | 41 条音频机器可读清单 |
| [产品规格](docs/产品规格.md) | 产品定位 + 模块 + 开发状态 |
| [项目结构说明](docs/项目结构说明.md) | 目录结构 + 文件说明 |
| [今日训练（打卡）](docs/功能模块文档/今日训练.md) | 打卡模块设计方案 |
| [API 接入文档](docs/API接入文档.md) | 所有 API 汇总 |

## 端口分配

| 服务 | 端口 |
|------|------|
| 本项目后端 | 8011 |
| 本项目前端 | 5185 |
| 上游 tianfu_rag | 8010 |
| MySQL | 3306（共用） |

详见 `D:\cursor\project\端口调用汇总.txt`
