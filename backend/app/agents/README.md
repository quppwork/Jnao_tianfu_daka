# Agent 层 · 架构分层

对齐六层：前端 → 接入 → 编排 → **Agent** → Harness → 能力。  
改码前先读项目 skill：`.cursor/skills/jnao-agent-layers/SKILL.md`（意图 → 层 → 路径）。

```
前端 (vue_fronted)
    ↕ HTTP / SSE / WS
接入层 (api/* + services CRUD)
    ↓
编排层 (harness/orchestration + shared/handoff + guide/pipeline)
    ↓
Agent 层（本目录五核：Role / Goal / 工具权限 / 产品闸门）
    ↓
Harness（loop / turn / tools / safety — 全 Agent 共享）
    ↓
能力层 (doubao_client / bailian / DB)
```

## 目录

```
app/agents/
├── shared/           # handoff / stage / talent（无业务决策）
├── qa/               # 学科答疑
├── guide/            # 首页引导
├── academy/          # 天赋学院角色
├── consult/          # 家长在线咨询（runner 出话）
├── parent_guide/     # 家长版大宇引导（runner 出话）
└── solve/            # 拍题领域 profile（与 QA 并列）
```

## 五路边界

| Agent | 出话 | 落库 Service | API |
|-------|------|--------------|-----|
| qa | `qa/runner.py` → `run_profile_turn` | `qa_service` | `api/qa.py` |
| guide | `guide/runner.py` | `guide_service` | `api/guide.py` |
| academy | `academy/harness.py` 等 | `services/academy/` | `api/academy.py` |
| consult | `consult/runner.py` | `consult_service` | `api/consult.py` |
| parent_guide | `parent_guide/runner.py` | `parent_guide_service` | `api/parent.py` |

- **Guide ↔ QA 互不 import runner**；联调靠 `shared/handoff` + 前端跳转。  
- **禁止**在 Agent 内直接 `httpx` 打模型；一律 Harness → `doubao_client`。  
- 产品闸门（错科、OCR 澄清、学院选角）留在各 Agent facade，不进 `loop` 内核。

## Harness / 能力（勿塞进本目录）

| 层 | 落点 |
|----|------|
| Loop / Turn | `app/harness/loop.py`、`turn.py` |
| 工具 MCP | `app/harness/tools/*`、`registry.py` |
| 契约校验 | `harness/contract.py`（`inputSchema` → `call_tool` 强制校验；`HARNESS_CONTRACT`） |
| Evidence | `harness/evidence.py`（内容哈希 + 账本；`HARNESS_EVIDENCE`；默认可换 Ledger） |
| 外部 MCP SDK | `harness/mcp_adapters/`（协议 + 注册表，后续挂第三方 Server） |
| LLM HTTP / 多 Key | `app/services/doubao_client.py`（多 Key 见 `docs/待开发.md`） |
| Profile 默认参 | `app/harness/llm.py` |

## 自研 vs 框架

主路径保持自研 ReAct（`iter_agent`）。是否引入 LangGraph/LangChain：  
问「业务复杂度是否已超过自研循环」，**不要**为对齐架构图而换框架。  
细则：`.cursor/skills/jnao-agent-layers/SKILL.md` §5。

## 产品需求对齐（2026-10 讨论稿 2.0）

| 模块 | 已落代码 | 仍依赖内容/后台 |
|------|----------|-----------------|
| 在线咨询 | 大宇/五者可答禁答 + 占位兜底（`llm_catalog`） | 两套已发布知识库元数据、正式兜底文案 |
| 天赋学院 | 角色边界 + 占位兜底（`academy/harness`） | 剧本/任务版本化发布后台、张总审核文案 |
| 学科引导 | 线索互动优先、不默认代答；学业规划闸（`check_academic_plan_ready`） | 正式「已确认规划」表、同类题质量校验、断线恢复 |

## 兼容

- `services/consult_agent.py` → 再导出 `agents.consult.runner`  
- `services/parent_guide_service` 保留会话 CRUD，并再导出 runner 符号供旧 import
