# Episode Packs（第二层：剧集讨论区配置）

一集一个目录。加载器：`loader.py`。

| 文件 | 职责 |
|------|------|
| `pack.yaml` | 频道 UI：标题、任务、chips、媒体、`knowledge_cutoff` |
| `knowledge.yaml` | 讨论料包：梗概 / 节拍 / 角色视角 / 可聊与勿提（与 UI 解耦） |

必填讨论字段：

- `characters_present` / `characters_absent`
- `knowledge_cutoff`
- `scene_context`
- `topic_hints`

加集：复制某集目录 → 改 `pack.yaml` + 填 `knowledge.yaml` → 填 `oss_key`。

角色卡见 `../cards/`；全局事件图见 `../world/events.yaml`；知识层说明见 `../knowledge/README.md`。
不在代码里写人设/约束/台词兜底。后续百炼学院库用 `BAILIAN_ACADEMY_INDEX_ID`，切片带 `episode_id` 元数据。
