# 后端测试说明

> 契约与单元测试以 `backend/tests` 为准；根目录 `tests/` 仅保留发烟 / 需本机起服的集成脚本。  
> AI 统一走 **DeepSeek**（OpenAI 兼容；单元测试默认 mock，不消耗额度）。

## 运行

```powershell
# 全量单元测试（推荐）
.\.venv\Scripts\python.exe -m pytest backend\tests -q

# 发烟（根目录，内存库）
.\.venv\Scripts\python.exe -m pytest tests\smoke_test.py -q

# 真实模型联调（消耗 API，需 backend/.env 配好 DEEPSEEK_API_KEY）
$env:DOUBAO_LIVE_TEST="1"   # 历史开关名，仍表示「真连上游」
.\.venv\Scripts\python.exe -m pytest backend\tests\test_doubao_live.py -v
```

## 前端模块 ↔ API ↔ 测试

| 前端 | 主要 API | 测试 |
|------|----------|------|
| 首页引导 | `/api/guide/*` | `test_module_home.py`、`test_guide_*.py` |
| 天赋测评 | `/api/talent/*` | `test_talent_api.py` |
| 今日训练 | `/api/training/*` | `test_training_*.py`、`test_round2_fixes.py` |
| 学科答疑 | `/api/qa/*` | `test_module_qa.py`、`test_qa_*.py` |
| 家长引导 / 咨询 | `/api/parent/*`、`/api/parent/consult/*` | `test_parent_*.py`、`test_harness_landing.py` |
| 登录注册 | `/api/auth/*` | `test_module_auth.py`、`test_wechat_auth.py` |
| Harness / 安全 | — | `test_harness*.py`、`test_harness_safety.py`、`test_security*.py` |

## Mock

| 依赖 | 位置 |
|------|------|
| JNAO 测评 | `conftest.mock_jnao` |
| DeepSeek（原豆包 mock 入口） | `conftest.mock_doubao` |
| DB | `sqlite:///:memory:` |

## 注意

- 旧 `POST /api/chat` 已删除；回归见 `test_module_home`。  
- 根目录 `tests/test_api_integration.py` / `test_workflow_e2e.py` 需本机 `8012` 起服，日常 CI 不跑。  
- Agent 分层改码见 `.cursor/skills/jnao-agent-layers/SKILL.md`。
