# 分集讨论知识（与 pack.yaml 解耦）

- `packs/<EP>/pack.yaml`：频道 UI、任务、chips、解锁媒体
- `packs/<EP>/knowledge.yaml`：本集可聊剧情料（摘要 / 节拍 / 角色视角 / 边界）

运行时：本地 YAML 必选注入；`BAILIAN_ACADEMY_INDEX_ID` 有值时再叠加检索，并按 `episode_id` / cutoff 裁剪。

后续补数据：只改或新增 `knowledge.yaml`，或往百炼库上传带 `episode_id` 元数据的切片。
