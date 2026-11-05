# 学院角色卡（人设层）

每张卡一个 `*.yaml`，由 `loader.py` 注入 system。

## 只写「你是谁」，不写「怎么调工具」

| 层 | 放哪 | 管什么 |
|----|------|--------|
| **人设** | 本目录 yaml | 身份、性格、说话、关系、示例口吻 |
| **干活** | academy graph / harness / KB | 剧集知识、分条、工具、剧情笔记 |

参考 QQ-Bridge `roles/` 的写法：去 AI 味、短句、示范语气、黑名单；**不要**抄群聊潜水 / SILENT / 表情包协议。

天赋底色以仓库 `02-五者天赋体系.md` 为准：绽放优点、管住缺点，不改成另一种天赋。

字段：`key` `name` `tag` `persona` `voice` `relations` `voice_samples` `appears_from` `appears_until` `in_channel`。
