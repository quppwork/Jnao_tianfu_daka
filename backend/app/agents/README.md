# Agent 层目录规划

面向「张宇老师」等多 Agent 场景：人设、情境、编排、只读工具从 `services/` 抽离；  
`services` 保留 HTTP/DB 落库与鉴权编排入口。

```
app/agents/
├── shared/                 # 跨 Agent 共用（无业务决策）
│   ├── stage.py / talent.py
│   └── handoff.py          # navigate 白名单 / situation 文案（Agent 间只交接动作）
├── qa/                     # 学科答疑 Agent（已有）
│   ├── persona.py
│   ├── subjects/
│   ├── router.py
│   ├── prompt_builder.py
│   └── memory.py
└── guide/                  # 首页引导 Agent
    ├── persona.py
    ├── context.py / situations.py / bootstrap.py
    ├── long_term.py        # 阶段 C：DB 长期摘要
    ├── runner.py           # 对话 + actions + 摘要注入
    ├── memory.py           # 会话截断 + bootstrap 日缓存/快照
    └── tools/              # 阶段 B 只读工具
```

## 多 Agent 边界（勿耦合）

- **Guide 与 QA 互不 import**；联调靠前端跳转 + `shared/handoff` 的 `navigate` 动作。  
- **禁止** `guide.runner` 调用 `qa.runner`（或反向）。  
- 先各自做完，再按需加 thin handoff；不要先做超级 Orchestrator。

## 职责边界

| 层 | 职责 |
|----|------|
| `api/guide.py` | 路由：session / bootstrap / chat；不写业务 |
| `services/guide_service.py` | 会话 CRUD、调 Agent、落库 |
| `agents/guide/*` | 情境、开场、对话、actions |
| `agents/shared/handoff.py` | 跨 Agent 跳转白名单 |

## 演进

### 已完成（Guide 主线）

1. **A0** 进页 bootstrap  
2. **A1** 对话注入情境  
3. **A2** actions 协议 + 轻状态条  
4. **B** `tools/*` 只读 tool-loop  
5. **B+** 前端吃满 `actions`；旧 `/api/chat` 已删  
6. **C** `long_term` + 日快照 + 评测抽检  
7. **UX** 会话管理 / 欢迎常驻 / 思考中 / 设置折叠（前端）

**主线无未完成阶段。** 可选增强与另线见下。

### 下一步（可选 / 另线，非 Guide 阶段债）

| 项 | 说明 |
|----|------|
| ~~设置「清除当前」与「清空全部」入口收敛~~ | ✅ 已做 |
| ~~真豆包话术抽检 / E2E~~ | ✅ `DOUBAO_LIVE_TEST=1` → `test_guide_live_quality.py` |
| ~~调试开关展示 tools_used~~ | ✅ 设置内开关 |
| 话术「先答后导」+ 训练逻辑模糊化 | ✅ persona / 工具摘要 / 去掉 consecutive_pass 外泄 |
| 原生 function-calling | 能力增强 |
| QA Agent 打磨 | **另线** |
| Orchestrator | **暂不做**（见 handoff 原则） |

详见 `docs/首页引导深化方案-2026-07-22.md` 文首「〇、状态总览」。
