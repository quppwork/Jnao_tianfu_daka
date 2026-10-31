# JNAO · Agent 基础架构

对照约定目录（Python 落点）：

```text
backend/app/
├── architecture/          # 【契约层】纯 Protocol
│   ├── llm_provider.py
│   ├── mcp_client.py
│   ├── memory_store.py
│   └── guard_policy.py
│
├── agent_core/            # 【核心协议模型】（图中 core/；与 app.core 平台工具分离）
│   ├── schemas/
│   │   ├── message.py
│   │   ├── tool_call.py
│   │   └── execution_state.py
│   └── events.py
│
├── harness/               # 【执行保障层】刹车 / 气囊 / 黑匣子
│   ├── guards/
│   │   ├── budget.py
│   │   ├── circuit_breaker.py
│   │   ├── timeout.py
│   │   ├── trace_recorder.py
│   │   └── permissions.py
│   ├── loop.py            # 底层 ReAct 实现细节（由 runtime 调用）
│   ├── policy.py / safety.py / approval.py / tools/ …
│   └── turn.py            # 兼容 shim → app.runtime
│
├── providers/             # 【外部适配器】
│   ├── llm/profile_router.py
│   └── mcp/gateway.py
│
├── memory/                # 【状态存储】只管存取
│   ├── checkpoint.py      # run 可恢复
│   ├── log_store.py       # 跨轮会话 → ThreadStore
│   └── adapters/          # guide / qa / report_talent
│
├── runtime/               # 【编排层】无脑跑循环
│   ├── executor.py        # 串 LLM + 工具 + Guards
│   └── public.py
│
├── assemble.py            # 【组装层】依赖注入 get_bundle()
│
├── model_cost/            # Fee（横切）
└── agents/                # 【业务板块】人设 / 情境 / 产品闸门；出话只调 runtime
    ├── guide/ qa/ parent_guide/ consult/ academy/ solve/
    └── ARCHITECTURE.md
```

---

## 依赖方向

```text
agents/* · services/*_agent
    →  runtime.run_turn / memory.ThreadStore / model_cost
    →  assemble.AgentBundle（guards · llm · mcp · checkpoint）
    →  architecture.*（契约）
禁止：业务直接散落 insert 会话表、旁路注入检测、旁路工具白名单
```

---

## 角色映射

| 角色 | 落点 |
|------|------|
| Orchestrator | `runtime.Executor` |
| Brain | `providers.llm` → `harness.llm` |
| Hands | `providers.mcp` + `harness.registry` |
| Constrainer | `harness.guards.*` |
| Memory | `memory.checkpoint` + `memory.log_store` |
| Fee | `model_cost` + `guards.budget` |
| Soft | profile system + tool description |

---

## 业务入口

```python
from app.runtime import run_turn, run_turn_stream
# 兼容：from app.harness.turn import run_profile_turn  （shim）
```

产品闸门（QA 错科等）仍由 facade 写入 `metadata.product_gate`，内核 `gates` 短接。

---

## 测试驱动（规范化准绳）

| 套件 | 覆盖 |
|------|------|
| `tests/test_agent_architecture.py` | guards / assemble / agents 禁止直连 harness.turn |
| `tests/test_agent_public_exports.py` | 包导出面不崩 |
| `tests/test_report_talent_api.py` | `GET/POST /api/talent/assessment/{id}/chat` |
| `tests/test_report_talent_agent.py` · `test_thread_store.py` | 会话隔离与拒答 |

单测统一 `patch("app.runtime.run_turn")`；`conftest` 每例 `reset_bundle()`。

---

## 板块会话 domain

| domain | thread_key |
|--------|------------|
| report_talent | assessment_id |
| guide / parent_guide | session_id |
| qa | session_id |
| consult / academy | 待补 adapter |
