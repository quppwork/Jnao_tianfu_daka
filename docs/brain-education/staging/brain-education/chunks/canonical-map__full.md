[脑科学教育 · 权威地图 · canonical-map.md · 整篇]

# 权威源地图（步骤 6 · Canonical Map）
> 日期：2026-08-31
> 输入：`staging/term_normalized/`
> 输出：`staging/canonical/`（已注入角色横幅）
## 主题 → 权威全文
| 主题 | 权威路径 |
|------|----------|
| 五力展开 | `foundations/talents.md` |
| 脑波/变聪明公式 | `foundations/theory.md` |
| 孩子单型怎么带 | `practice/talents-application.md` |
| 家长×孩子话术 | `practice/parent-child/` |
| 训练方法/九段 | `training/methods.md` |
| 训练安全异常 | `training/safety.md` |
| 修炼总诀用词 | `foundations/talents.md` |
## 文件角色一览
| 文件 | 角色 | 主题 | 去重/参见 |
|------|------|------|-----------|
| `delivery/delivery-escort-sop.md` | `unique` | 护航SOP | — |
| `delivery/training-system-framework.md` | `unique` | 交付框架标准 | 训练方法/九段→`training/methods.md` |
| `foundations/talents.md` | `canonical` | 五力展开、修炼总诀用词、五者画像 | — |
| `foundations/theory.md` | `canonical` | 脑波/变聪明公式、大脑理论总框架 | 五力展开→`foundations/talents.md` |
| `frontline/cases.md` | `unique` | 案例索引 | — |
| `frontline/products.md` | `unique` | 产品线 | — |
| `frontline/quotes.md` | `unique` | 金句口播 | — |
| `frontline/sales.md` | `unique` | 跨组合招生通则 | 家长×孩子话术→`practice/parent-child/` |
| `frontline/technology.md` | `summary_of` | 设备形态/科技话术 | 脑波/变聪明公式→`foundations/theory.md` |
| `glossary.md` | `glossary` | 术语表 | — |
| `meta/sources.md` | `index` | 资料溯源 | — |
| `meta/transcript-screening-2026-08-28.md` | `index` | 转写筛选说明 | — |
| `practice/learning-methods.md` | `summary_of` | 学习方法/态度系统 | 孩子单型怎么带→`practice/talents-application.md` |
| `practice/parent-child/de-si.md` | `canonical` | 家长×孩子话术、德者×思者 | — |
| `practice/parent-child/xue-si.md` | `canonical` | 家长×孩子话术、学者×思者 | — |
| `practice/parent-child/ying-xing.md` | `canonical` | 家长×孩子话术、赢者×行者 | — |
| `practice/talents-application.md` | `canonical` | 孩子单型怎么带 | — |
| `README.md` | `index` | 知识包总索引、口径裁定纪要入口 | — |
| `training/examples/training-plan-winner-girl-10yo.md` | `unique` | 个案训练方案范例 | 训练方法/九段→`training/methods.md` |
| `training/methods.md` | `canonical` | 训练方法/九段 | — |
| `training/safety.md` | `canonical` | 训练安全异常 | — |
## 处理策略说明
1. **不删除**非权威文件中的长文（避免误删独特表述），改为注入「去重提示 / 摘要提示」。
2. 入库时建议：`role=canonical` 全文分块；`summary_of` 可降权或仅保留带提示的摘要段。
3. `unique` / `index` / `glossary` 按自身主题入库，不与上表权威主题抢全文。
4. 亲子话术权威目录本批仅含 3 个已填格；其余占位格仍在 hold_draft。
