# 后端测试说明

> 测试先行：每个前端页面都有对应的后端契约测试  
> AI 统一走 **豆包 Ark**（单元测试默认 mock，不消耗额度）
> **当前：290+ 用例 / 52 文件 / 0 跳过（v2.0 多技能并行 Tier 晋级）**

## 运行

```powershell
# 全量单元测试（推荐，mock JNAO + 豆包）
.\.venv\Scripts\python.exe -m pytest backend\tests -v

# 仅某个前端模块
.\.venv\Scripts\python.exe -m pytest backend\tests\test_module_training.py -v

# 端到端流程
.\.venv\Scripts\python.exe -m pytest backend\tests\test_e2e_flows.py -v

# 真实豆包联调（消耗 API，需 backend/.env 配好 Key）
$env:DOUBAO_LIVE_TEST="1"
.\.venv\Scripts\python.exe -m pytest backend\tests\test_doubao_live.py -v

# Guide 真豆包话术抽检（五 situation + 工具探针，打印回复便于人工看文笔）
$env:DOUBAO_LIVE_TEST="1"
.\.venv\Scripts\python.exe -m pytest backend\tests\test_guide_live_quality.py -v -s
```

## 前端模块 ↔ API ↔ 测试文件

| 前端页面 | 主要 API | 测试文件 |
|----------|----------|----------|
| `pages/index.vue` 首页 | `POST /api/guide/chat` | `test_module_home.py` |
| `pages/talent/index.vue` 天赋测试 | `POST /api/talent/report` | `test_module_talent.py`, `test_talent_api.py` |
| `pages/report/index.vue` 报告 | 测评结果来自 talent API | `test_module_talent.py` |
| `pages/training/index.vue` 今日训练 | `/api/training/*` | `test_module_training.py`, `test_training_api.py`, `test_training_api_v2.py`, `test_training_child_guide.py`, `test_training_closed_loop.py`, `test_training_day.py`, `test_talent_content_pool.py`, `test_training_carryover.py`, `test_training_day_settlement.py`, `test_training_yesterday_context.py`, `test_training_formula_engine.py`, `test_training_mastery.py`, `test_training_schedule.py`, `test_training_state_v2.py` |
| `pages/qa/index.vue` 学科答疑 | `POST /api/qa/chat` | `test_module_qa.py`, `test_qa_agent_prompts.py`, `test_qa_agent_router.py`, `test_qa_coach.py`, `test_qa_enhanced.py`, `test_qa_prompt_builder.py`, `test_qa_rag_router.py`, `test_qa_coach_context.py` |
| `pages/growth/index.vue` 成长里程碑 | `/api/growth/*` | `test_module_growth.py` |
| `pages/login/` 用户注册+引导 | `/api/auth/*`, `/api/user/profile` | `test_module_auth.py`, `test_workflow_onboarding.py`, `test_onboarding_returning.py`, `test_user_profile_merge.py` |
| 资源库 | `/api/resources/*` | `test_training_api.py` |
| 健康检查 | `GET /api/health` | `test_health_api.py` |
| 开发者工具 | `/api/dev/*` | `test_dev_api.py` |
| 安全校验 | — | `test_security.py` |
| 内容导入 | — | `test_catalog_import.py`, `test_single_file_skill_match.py` |
| 豆包客户端 | — | `test_doubao_client.py`, `test_doubao_live.py` |
| 端到端 | 全链路 | `test_e2e_flows.py` |

## 端到端

`test_e2e_flows.py` 覆盖 MVP 闭环：

```
注册 → 首页引导 → 天赋测评 → 今日训练 → AI报告 → 打卡 → 学科答疑 → 成长徽章
```

## Mock 策略

| 依赖 | Mock 位置 | 说明 |
|------|-----------|------|
| JNAO 测评 | `conftest.mock_jnao` | 不调 m.jnao.com |
| 豆包 AI | `conftest.mock_doubao` | 全平台 AI 统一 mock |
| MySQL | `sqlite:///:memory:` | 测试隔离 |

## AI 路由（生产）

| 功能 | 路径 | 提供商 |
|------|------|--------|
| 首页引导 | `/api/guide/chat`、`/api/guide/chat/stream` | 豆包（情境 + 只读工具） |
| 学科答疑 | `/api/qa/chat` | 豆包 + 天赋提示词 |
| 训练日报 | `/api/training/report/today` | 豆包 |

> 旧 `POST /api/chat` / `GET /api/chat/stream` 已废弃删除，勿再调用。
