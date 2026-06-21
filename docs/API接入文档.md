# API 接入文档

> 最后更新：2026-06-21  
> 本文档汇总本项目所有外部依赖 API 及内部 API

---

## 第一部分：外部 API — JNAO 天赋测评

> 基础地址：`https://m.jnao.com`  
> 基于劲脑官方说明 + 本项目联调实测整理

### 整体流程

```
用户答完 35 题（是/否）
    │
    ▼
① GET submitanswer  →  返回 data.id（劲脑测评记录 ID）
    │
    ├─ ② 将 data.id 写入本地会话
    │
    ├─ ③ 官方报告页（推荐）
    │      GET parent_test_result.html?id={data.id}
    │
    └─ ④ 应用内报告（本项目）
           testresult JSON 接口已下线 → 本地模板回退
```

### 提交答案 `submitanswer`

**请求：**

| 项 | 值 |
|---|---|
| 方法 | `GET` |
| 路径 | `/h5/adult/submitanswer` |
| 完整示例 | `https://m.jnao.com/h5/adult/submitanswer?answer=11000111110001001001011111000101001&uid=1&type=0` |

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `answer` | string | 是 | **35 位** `0`/`1` 字符串，按题号 1→35 顺序拼接 |
| `uid` | int | 是 | 用户唯一标识 |
| `type` | int | 是 | `0` = 成人测评，`1` = 儿童测评 |

**编码规则：**

| 用户选择 | 编码 |
|---------|------|
| 完全符合 | `1` |
| 有差异 | `0` |

**响应（实测）：**

```json
{
  "code": 1,
  "msg": "ok",
  "data": { "id": "76" },
  "url": ""
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | int | `1` 或 `10` = 成功 |
| `data.id` | string | 测评记录 ID，后续查报告用 |

### 查看官方报告

| 项 | 值 |
|---|---|
| 路径 | `/h5/parent_test_result.html?id={记录ID}` |
| 注意 | 微信内打开体验最完整；普通浏览器可能只显示骨架 |

### JSON 报告接口 `testresult`（已下线）

```
GET /h5/Adult/testresult?id={记录ID}
→ HTTP 404 或 JSON 错误
→ 不可作为生产依赖
```

### 本地报告回退

当 `testresult` 不可用时，本项目使用本地数据模板生成报告。

### 报告数据结构参考

**五大天赋属性（Attribute）：** 思者(A)、赢者(B)、德者(C)、行者(D)、学者(E)、迷者(F，仅儿童)

**四项能力雷达（Ability）：** 创新力、领导力、公信力、执行力（各含 grade、value 0-100）

**综合状态（State）：** 相争、难辨、牵制、孤显、双生、本命、无向、无神

---

## 第二部分：外部 API — tianfu_rag AI 对话

> 基础地址：`http://192.168.60.199:8010`（本地开发可用 `http://127.0.0.1:8010`）  
> 本项目通过后端代理调用，前端不直接访问

### 基本信息

| 项目 | 说明 |
|------|------|
| 协议 | HTTP/1.1 + JSON |
| 流式 | SSE (`text/event-stream`) |
| 鉴权 | `RAG_API_SECRET` 环境变量（非空则需 `X-API-Key` header） |

### 核心对话接口

**`POST /chat` — 同步对话**

最简请求：
```json
{
  "message": "string",
  "user_id": "string",
  "user_department": "general"
}
```

响应：
```json
{
  "answer": "string",
  "sources": ["string"],
  "source_refs": [{ "source": "", "parent_id": "", "department": "" }],
  "rewritten_query": "string | null",
  "answer_mode": "string | null",
  "verified": true | false | null
}
```

**`POST /chat/stream` — SSE 流式对话**

请求体同 `/chat`。响应为 SSE 事件流：

| event type | 字段 | 说明 |
|------|------|------|
| `token` | `content` | 逐 token 文本 |
| `done` | `answer`, `sources`, `source_refs`, `rewritten_query`, `answer_mode`, `trace_id` | 流结束 |
| `error` | `message`, `trace_id` | 错误 |

### 本项目使用的接口

| 方法 | 路径 | 用途 |
|------|------|------|
| `POST` | `/chat` | 学科答疑 — 同步问答 |
| `POST` | `/chat/stream` | 学科答疑 — 流式对话 |
| `GET` | `/health` | 健康检查 |

### 本项目未使用但可用的接口

| 类别 | 接口 | 说明 |
|------|------|------|
| 会话管理 | `/chat/sessions` 系列 | 对话历史持久化 |
| 用户反馈 | `/feedback` 系列 | 评分+纠错 |
| 文档入库 | `/ingest/*` | 知识库入库 |
| 配置管理 | `/config/*` | 模型、UI、向量库配置 |

---

## 第三部分：本项目内部 API

> 后端地址：`http://127.0.0.1:8011`  
> 框架：FastAPI + Uvicorn

### 现有接口

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| `GET` | `/api/health` | 健康检查 + 各集成状态 | ✅ |
| `POST` | `/api/talent/report` | 提交答案 → 获取报告（JNAO 代理） | ✅ |
| `POST` | `/api/talent/jnao/submit` | 代理提交到 JNAO | ✅ |
| `GET` | `/api/talent/jnao/report/{id}` | 获取 JNAO 报告 | ✅ |
| `POST` | `/api/chat` | 同步 AI 对话（代理到 tianfu_rag） | ✅ |
| `GET` | `/api/chat/stream` | SSE 流式对话 | ✅ |

### 待开发接口

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|------|
| `GET` | `/api/training/today` | 获取今日训练方案 | P0 |
| `POST` | `/api/training/step/{id}/complete` | 标记训练步骤完成 | P0 |
| `POST` | `/api/training/checkin` | 提交打卡 | P0 |
| `GET` | `/api/training/history` | 打卡历史 | P1 |
| `POST` | `/api/auth/login` | 用户登录 | P1 |
| `GET` | `/api/milestones` | 获取里程碑列表 | P2 |
| `GET` | `/api/growth/timeline` | 成长时间线 | P2 |

---

## 本地开发地址汇总

| 服务 | 地址 |
|------|------|
| 本项目后端 API | http://127.0.0.1:8011 |
| 本项目前端 H5 | http://127.0.0.1:5185 |
| API 文档 (Swagger) | http://127.0.0.1:8011/docs |
| 健康检查 | http://127.0.0.1:8011/api/health |
| 上游 tianfu_rag | http://192.168.60.199:8010 |

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-21 | 合并 API参考.md（tianfu_rag）与 api_talent_integration.md（JNAO），新增本项目 API 章节 |
| 2026-06-18 | 初版：确认 JNAO submitanswer 格式、testresult 下线 |
