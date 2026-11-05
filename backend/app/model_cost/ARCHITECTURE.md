# model_cost · Fee 横切层

> 回答：**用量与费用数据属于 Agent 架构的哪一层？**  
> **Fee（费用横切）** — 包路径 `app/model_cost`。  
> 不是 Agent 人设层，不是 Harness 循环内核，不是编排 handoff。  
> 落库与额度账本落在**能力层 / 数据层**；对外查询落在**接入层**。

对照全仓：`backend/app/agents/ARCHITECTURE.md` 角色表中的 **Fee**。

---

## 1. 角色定位

| 角色 | 职责 | 不做什么 |
|------|------|----------|
| **Fee / CostMeter** | 定义「记一笔费用」的契约与板块维度；价目换算；按 feature 汇总 | 不写人设、不问第几题、不跑 ReAct |
| **能力层 LLM Client** | 调 DeepSeek 等官网接口，拿回 `usage`，副作用调用记费 | 不算价、不扣用户额度 |
| **能力层 Persistence** | `usage_recorder` 写 `UpstreamUsageEvent`；`credit_service` 管 `CreditAccount` | 不感知具体 Agent 话术 |
| **Harness Guard（budget）** | 运行中预算/步数刹车（可选） | 不替代人民币账本 |
| **接入层** | `GET /api/usage/*` 看板；各 Agent API 入口 `require_credit` | 不拼费率表、不直接 insert 用量行 |
| **Agent 层** | 最多 `bind_feature(AgentFeature.XXX)` 或经工具 `CostEvent` | 禁止 import `usage_recorder` / 改价目 |

依赖方向（只准向下）：

```text
agents / harness.tools
    →  architecture.CostMeter  /  model_cost.CostRecorder（协议）
    →  model_cost.UsageLedger
    →  services.usage_recorder + model_cost.rates
    →  db.UpstreamUsageEvent / CreditAccount

api/usage · api/{qa,guide,…}
    →  model_cost.summarize  /  credit_service.require_credit
```

---

## 2. 数据依赖

| 数据 | 表 / 字段 | 谁写 | 谁读 |
|------|-----------|------|------|
| 调用计量 + 成本快照 | `upstream_usage_event`（token、`cost_milli_cent`、`rate_version`、`feature`、`billing_parent_id`） | `usage_recorder.record_usage`（LLM/RAG 成功路径） | wallet / events / by-feature / admin |
| 会员额度账本 | `credit_account`（月度点、充值余额） | `credit_service` | wallet、`require_credit` |
| 价目版本 | 代码内 `rates.RATE_VERSION`（非用户表） | 发版改代码 | 写入每条 event 快照 |
| 上游 usage | DeepSeek/百炼响应 `usage`（含 cache hit） | 厂商 API | client → recorder → rates |

原则：**成本以落账瞬间的官价快照为准**（峰谷 + 缓存命中），看板汇总加总 `cost_milli_cent`，事后不重算改写历史行。

百炼**知识库规格费**（元/库/小时）不在本层；对话/检索 token 另记。

---

## 3. 组件与类

```text
architecture/
  cost_meter.py          CostMeter（Protocol）— 契约层

model_cost/              Fee 实现包（横切）
  protocols.py           CostEvent / CostSummary / CostRecorder
  features.py            AgentFeature（板块枚举）
  rates.py               ModelRate / RateCard / estimate_usage_cost
  ledger.py              UsageLedger（CostRecorder 默认实现）
  __init__.py            get_cost_recorder()

services/                能力层（持久化与额度，非 Agent）
  usage_recorder.py      record_usage / 家计聚合
  credit_service.py      require_credit / wallet payload
  doubao_client.py       DeepSeek 调用后 record_usage（provider=deepseek）

api/
  usage.py               接入：summary / wallet / by-feature / events
```

| 类 / 函数 | 层 | 功能 |
|-----------|----|------|
| `CostMeter` / `CostRecorder` | 契约 | `record` / `bind_feature` / `summarize` |
| `CostEvent` | Fee DTO | 一次上游调用的计量载荷 |
| `AgentFeature` | Fee 维 | guide / qa / academy / … 聚合键 |
| `ModelRate` / `RateCard` | Fee 价目 | 多模型官网价；峰谷；缓存命中 |
| `estimate_usage_cost` | Fee | `(milli_cent, rate_version)` |
| `UsageLedger` | Fee 实现 | 委托 recorder；汇总用库内快照 |
| `record_usage` | 能力 | 写 event + 调价目 |
| `require_credit` | 能力 + 接入门闸 | `CREDIT_ENFORCE` 时拦截 |
| `build_wallet_payload` | 能力 | 家计 token/¥ + 额度 |

---

## 4. 与分层 skill 的映射

| 用户意图 | 主层 | 落点 |
|----------|------|------|
| 换模型 / 官价 / 多模型费率 | **Fee + 能力** | `model_cost/rates.py`、`doubao_client` 默认 model |
| 看板看每人费用 | **接入** | `api/usage.py` + 静态 `usage-board.html` |
| 扣额度 / 月度点 | **能力** | `credit_service`；API 入口薄调 |
| Agent 对话逻辑 | **Agent** | 禁止改费率 |
| 循环步数预算 | **Harness guards** | `guards/budget.py`（与人民币账本解耦） |

---

## 5. 功能归属（feature）

每条 `upstream_usage_event.feature` 标明产生费用的产品功能。

| 写入方式 | 何时 |
|----------|------|
| API `bind_usage_feature("qa"…)` | guide / qa / academy / solve / parent_* |
| `get_cost_recorder().bind_feature(REPORT_TALENT)` | 报告天赋解答 |
| Harness `feature=harness.{profile}` | 经 normalize 去掉 `harness.` 前缀 |
| 百炼 retrieve/search/knowledge_chat/generate | **优先上下文 feature**；无则 `rag` |

看板：`GET /api/usage/by-feature`、`/events` 的 `feature` / `label` 列。

## 6. 红线

1. Agent / runner **不得**直接写 `UpstreamUsageEvent` 或改 `rates.py` 业务分支。  
2. 费率只认**官网模型 id**（如 `deepseek-flash`）；豆包停用，不作默认 provider。  
3. 历史行的 `cost_milli_cent` 不因调价回溯；升 `RATE_VERSION` 只影响新事件。  
4. `CREDIT_ENFORCE` 默认关；打开后拦截在接入层，计算仍在能力层。  
5. 百炼调用**禁止**写死 `feature="rag"` 盖掉调用方板块（无上下文时才用 `rag`）。
