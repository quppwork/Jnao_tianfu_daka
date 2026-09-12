# 外部接入与上游 API

> **文档地位**：整理本仓库**对外依赖**（大模型 / RAG / 语音 / 业务上游 / 云资源），便于联调与排障。  
> **非范围**：本系统对外暴露的业务 REST 清单见产品侧「前端后端 API」文档；Agent 内部模块边界见 `backend/app/agents/README.md`。  
> **配置模板**：`backend/.env.example` · 接入状态机：`backend/config/integration.yaml`  
> **整理日期**：2026-09-03

---

## 1. 总览

```text
┌─────────────────────────────────────────────────────────────┐
│  JNAO 本系统（FastAPI :8012 + UniApp :5185）                 │
├──────────────┬──────────────┬──────────────┬────────────────┤
│ 火山豆包 Ark │ 阿里云百炼   │ m.jnao.com   │ 阿里云 OSS     │
│ （主 LLM）   │ （引导 RAG） │ （天赋测评） │ （训练媒体）   │
├──────────────┼──────────────┼──────────────┼────────────────┤
│ 企业 RAG     │ 火山语音     │ 微信 / 短信  │ 企微（运维）   │
│ TIANFU_RAG   │ ASR（可选）  │ OAuth / SMS  │ 客户同步工具   │
│ （答疑遗留） │              │              │                │
└──────────────┴──────────────┴──────────────┴────────────────┘
```

**按产品功能串线：**

| 功能 | 主要外接 |
|------|----------|
| 首页引导 Guide | 豆包 + 百炼（KB Agent / Retrieve） |
| 学科答疑 QA | 豆包；（可选）旧 `TIANFU_RAG` |
| 学业规划 | 豆包单次生成（无 RAG、无 Agent 循环） |
| 天赋测评 | `https://m.jnao.com` |
| 今日训练媒体 | 阿里云 OSS 签名/列举 |
| 语音输入 | 火山 ASR（需单独配） |
| 家长登录 | 微信 OAuth / 短信（可 mock） |

本仓库**不**依赖：自托管 LoRA、LangChain/LangGraph 运行时、Cursor `.mcp.json`（仅编辑器侧）。

---

## 2. 大模型

### 2.1 火山引擎豆包（主 LLM）— live

| 项 | 说明 |
|----|------|
| 用途 | Guide / QA / bootstrap / 学业规划 / 可选 Vision 拍图；Guide 工具 FC |
| Base | `DOUBAO_API_BASE`（默认 `https://ark.cn-beijing.volces.com/api/v3`） |
| 鉴权 | `DOUBAO_API_KEY` |
| 模型 | `DOUBAO_CHAT_MODEL`、`DOUBAO_VISION_MODEL` |
| 代码 | `backend/app/services/doubao_client.py` |
| 能力探测 | `is_configured()`；Guide debug：`GET /api/guide/debug`（需开调试路由） |

主要封装：

- `chat_completion` / `chat_completion_stream`
- `chat_completion_message`（原生 function-calling）
- `vision_chat_completion`（拍图）

用量记录落地（规划，含豆包 LLM + 百炼 RAG）：见 [LLM用量记录落地步骤.md](./LLM用量记录落地步骤.md)。

### 2.2 DeepSeek（备用）— 配置位存在

| 项 | 说明 |
|----|------|
| 环境变量 | `DEEPSEEK_API_KEY` / `DEEPSEEK_API_BASE` / `DEEPSEEK_CHAT_MODEL` |
| 现状 | 非主链路；主对话走豆包 |

---

## 3. RAG / 知识库

### 3.1 阿里云百炼（引导主 RAG）— 可配置 live

| 项 | 说明 |
|----|------|
| 用途 | 首页知识问答：练法视频库 / 天赋文档库 |
| Workspace | `BAILIAN_WORKSPACE_ID`（或 `WORKSPACE_ID`） |
| API Host | `BAILIAN_API_HOST`（可按 workspace 拼 `*.cn-beijing.maas.aliyuncs.com`） |
| DashScope | `DASHSCOPE_API_KEY`（`knowledge/chat`、Search 必填） |
| 文档索引 | `BAILIAN_INDEX_ID` |
| 视频索引 | `BAILIAN_VIDEO_INDEX_ID`（训练 RAG / 视频源） |
| 知识问答 aid | `BAILIAN_KB_QA_DOC_AID` / `BAILIAN_KB_QA_VIDEO_AID`（可覆盖 `kb_registry.yaml`） |
| OpenAPI AK | `ALIBABA_CLOUD_ACCESS_KEY_*`（可回退 `OSS_ACCESS_KEY_*`） |
| 开关 | `GUIDE_KB_AGENT`（默认开）、`GUIDE_RAG_ENABLED`、`GUIDE_RAG_MODE=retrieve\|search` |
| 直答生成 | `BAILIAN_RAG_GENERATE`（0=Retrieve+豆包；1=百炼 file_search 直答） |
| 代码 | `backend/app/services/bailian/`、`knowledge/`、`agents/guide/kb_agent.py` |
| 选库目录 | `backend/data/kb_registry.yaml` |
| 就绪判断 | `guide_kb_agent_ready()` / `guide_rag_ready()` / `bailian_status()` |

**两条引导知识路径：**

1. **KB Agent（推荐）**：豆包选 `source_key` → 百炼 `POST .../api/v2/apps/knowledge/chat`  
2. **Legacy Retrieve**：百炼切片 → 注入 prompt → 豆包生成  

编排路由：`backend/app/agents/guide/pipeline.py`（`KB_AGENT` / `LEGACY_RAG` / `QA_HANDOFF` / `MINIMAL`）。

### 3.2 企业 RAG `TIANFU_RAG`（答疑遗留）— 常 mock

| 项 | 说明 |
|----|------|
| 用途 | 学科答疑教学法知识（旧路径） |
| URL | `TIANFU_RAG_URL`（默认 `http://127.0.0.1:8010`） |
| 鉴权 | `RAG_API_SECRET` → Header `X-API-Key` |
| Mock | `TIANFU_RAG_MOCK=1` 时视为不可用（本地推荐） |
| 代码 | `backend/app/services/qa_rag_client.py` |
| Health 引用 | `integration.yaml` → `GET {TIANFU_RAG_URL}/health` |

引导页完整 RAG **已迁百炼**；答疑后续可切百炼 QA 索引，此前仍指向本服务。

### 3.3 训练页 RAG — 可选

| 项 | 说明 |
|----|------|
| 开关 | `TRAINING_RAG_ENABLED` |
| 依赖 | Retrieve 就绪 + `BAILIAN_VIDEO_INDEX_ID` |
| 就绪 | `training_rag_ready()` |

---

## 4. 语音

| 接入 | 状态 | 环境变量 | 本系统接口 |
|------|------|----------|------------|
| 火山 ASR | 需单独申请；未配则不可用 | `SPEECH_APP_ID` / `SPEECH_ACCESS_TOKEN` | `POST /api/voice/asr`（live） |
| TTS | **deprecated**，前端未接 | 同上 | `POST /api/voice/tts` |

---

## 5. 业务上游与云资源

### 5.1 JNAO 官网 API（天赋测评）— live

| 项 | 说明 |
|----|------|
| Base | `https://m.jnao.com` |
| 提交答案 | `GET /h5/adult/submitanswer` |
| 拉取报告 | `GET /h5/Adult/testresult` |
| 代码 | `backend/app/services/jnao_client.py` |
| 本系统入口 | `POST /api/talent/report` 等 |

另：微信缺手机号时可跳转  
`WECHAT_BIND_MOBILE_URL`（默认 `https://m.jnao.com/home/member/bindmobile.html`）。

### 5.2 微信服务号 OAuth — live（需配 AppId）

| 环境变量 | 说明 |
|----------|------|
| `WECHAT_MP_APP_ID` / `WECHAT_MP_APP_SECRET` | 服务号 |
| 本系统 | `POST /api/auth/wechat/*` |

### 5.3 短信 — live（开发可 mock）

| 环境变量 | 说明 |
|----------|------|
| `SMS_PROVIDER=mock\|aliyun` | 开发常用 mock |
| `SMS_MOCK_CODE` / `AUTH_CHALLENGE_MOCK` | 本地验证码 |
| 生产 | `ALIYUN_SMS_*`（可复用 OSS AK） |
| 本系统 | `POST /api/auth/sms/*` |

> 微信内缺手机号走 m.jnao.com 绑手机页，不经短信模块。

### 5.4 阿里云 OSS（训练媒体）— live

| 环境变量 | 说明 |
|----------|------|
| `OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET` | 只读列举与签名 |
| `OSS_BUCKET` / `OSS_ENDPOINT` / `OSS_PREFIX` | 桶与前缀 |
| `OSS_SIGNED_URL` / `OSS_SIGN_EXPIRES` | 播放签名 |

用户业务数据**不上传** OSS。AK 亦可回退给百炼 OpenAPI。

### 5.5 企业微信 — 运维工具

| 环境变量 | 说明 |
|----------|------|
| `WEWORK_CORPID` / `WEWORK_CORPSECRET` / `WEWORK_AGENTID` | 客户联系等 |
| 代码 | `backend/tools/wework/`、`scripts/cron/` |

非 App 主链路；用于同步/运营脚本。

### 5.6 Redis — 可选

| 环境变量 | 说明 |
|----------|------|
| `REDIS_URL` | 多 worker 下限流 / OAuth 状态共享 |
| 未配时 | 直读 DB；启动日志会告警 |

### 5.7 数据库

| 环境变量 | 说明 |
|----------|------|
| `DATABASE_URL` | MySQL 或 `sqlite:///./data/jnao_daka.db` |
| `LEGACY_DATABASE_URL` | 历史库（绑手机等场景，按需） |

本地开发若 MySQL 密码不通，应改回 SQLite（见运维排障记录）。

---

## 6. 本系统相关 HTTP（对外能力入口）

以下为**本后端**暴露、会触发上游调用的接口（鉴权略，详见业务 API 文档）：

| 方法 | 路径 | 上游 |
|------|------|------|
| POST | `/api/guide/chat` · `/api/guide/chat/stream` | 豆包 ± 百炼 |
| POST | `/api/guide/bootstrap` | 豆包（失败模板兜底） |
| GET | `/api/guide/debug` | 探测豆包/百炼就绪（调试开关） |
| POST | `/api/qa/chat` · stream | 豆包 ± TIANFU_RAG |
| GET | `/api/growth/academic-plan` | 豆包单次（可缓存） |
| POST | `/api/talent/report` | m.jnao.com |
| POST | `/api/voice/asr` | 火山语音 |
| GET | `/api/health` | 含 integrations / 可选 RAG health |
| GET | `/api/meta/version` | 无上游，发版/boot_id |

---

## 7. 环境变量速查（AI / RAG）

```bash
# 豆包
DOUBAO_API_BASE=
DOUBAO_API_KEY=
DOUBAO_CHAT_MODEL=
DOUBAO_VISION_MODEL=

# 百炼
BAILIAN_WORKSPACE_ID=
BAILIAN_API_HOST=
BAILIAN_INDEX_ID=
BAILIAN_VIDEO_INDEX_ID=
BAILIAN_KB_QA_DOC_AID=
BAILIAN_KB_QA_VIDEO_AID=
DASHSCOPE_API_KEY=
GUIDE_KB_AGENT=1
GUIDE_RAG_ENABLED=0
GUIDE_RAG_MODE=retrieve
BAILIAN_RAG_GENERATE=0
TRAINING_RAG_ENABLED=0

# 旧企业 RAG
TIANFU_RAG_URL=http://127.0.0.1:8010
TIANFU_RAG_MOCK=1
RAG_API_SECRET=
```

完整注释见 `backend/.env.example`。

---

## 8. 代码索引

| 路径 | 职责 |
|------|------|
| `app/services/doubao_client.py` | 豆包 HTTP 客户端 |
| `app/services/bailian/` | 百炼 Retrieve / Search / knowledge_chat / 配置 |
| `app/services/knowledge/` | `KnowledgeBackend` 抽象（可替换实现） |
| `app/agents/guide/kb_agent.py` | 引导 KB Agent |
| `app/agents/guide/pipeline.py` | 引导路径路由 |
| `app/agents/guide/runner.py` | 引导编排 |
| `app/agents/qa/runner.py` | 答疑编排 |
| `app/services/qa_rag_client.py` | 旧 TIANFU_RAG |
| `app/services/academic_plan_service.py` | 学业规划（单次豆包） |
| `app/services/jnao_client.py` | 天赋测评上游 |
| `config/integration.yaml` | 接入状态声明 |
| `data/kb_registry.yaml` | 百炼选库目录 |

---

## 9. 本地联调检查清单

1. `DOUBAO_API_KEY` + 模型 id 有效 → Guide/QA/学业规划可生成  
2. `BAILIAN_WORKSPACE_ID` + `DASHSCOPE_API_KEY` + registry/aid → `guide_kb_agent_ready()==True`  
3. 无本地 `8010` 时设 `TIANFU_RAG_MOCK=1`，避免 health/答疑空转  
4. OSS AK 有效 → 训练音频可播  
5. `DATABASE_URL` 指向可连库（本地常用 SQLite）  
6. `GET /api/health`、`GET /api/guide/debug`（调试开）确认 integrations  

---

## 10. 明确不做 / 非本系统运行时依赖

- Cursor **MCP**（`.mcp.json`）— 编辑器工具协议，不参与 App 请求  
- **LangChain / LangGraph** — 当前 Agent 为自研编排  
- **LoRA 微调权重** — 未接入；知识靠 RAG + 提示词  
- TTS 前端接入 — 已标 deprecated  
