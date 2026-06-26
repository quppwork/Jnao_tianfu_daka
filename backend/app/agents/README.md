# Agent 层目录规划

面向「张宇老师」等多 Agent 场景，将提示词、路由、记忆从 `services/` 中抽离，便于后续扩展工具调用、多步编排。

```
app/agents/
├── shared/           # 跨 Agent 共用（学段、天赋画像）
├── qa/               # 学科答疑 Agent
│   ├── persona.py    # 公共人设
│   ├── subjects/     # 分学科角色与答题规范（math / chinese / english / science）
│   ├── router.py     # 学科识别与错频道提醒
│   ├── prompt_builder.py
│   └── memory.py     # qa_session / qa_message 记忆封装
└── guide/            # 首页引导 Agent
    ├── persona.py
    └── memory.py     # 待迁移
```

**演进路径：** services 保留 HTTP/DB 编排；Agent 层负责人设、路由、记忆；后续可在各 Agent 下增加 `tools/`、`graph.py` 等编排入口。
