# Episode Packs（第二层：剧集讨论区配置）

一集一个目录。加载器：`loader.py`。

必填讨论字段（对齐 `架构和技术栈.txt`）：

- `characters_present` / `characters_absent`
- `knowledge_cutoff`
- `scene_context`
- `topic_hints`

加集：复制 `E14/pack.yaml` → 改 id 与上述字段 → 填 `oss_key`。

角色卡见 `../cards/`；全局事件图见 `../world/events.yaml`。
不在代码里写人设/约束/台词兜底。
