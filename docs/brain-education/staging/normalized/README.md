# 脑科学教育知识体系

整理自：线下大会演讲转写 + 《天赋物语》短剧素材 + 《超脑进化之书》精读 + 同事张宇汇总资料包。

> **入库前必读（文档预处理）**：进入任意知识库之前，须按
> 《文档预处理规范》（文档预处理规范（仓库流程文档，非知识正文））
> 完成语料盘点→清洗→归一→分块→元数据→Staging 导出。
> **我们只做文档预处理**；向量化、建索引、平台入库由接手方完成。

> **怎么用本库**：先看下面「五层地图」→ 再按场景点进对应目录。
> **怎么扩写**：见 _templates/（扩写模板（本批未收录））；口径冲突先查文末「裁定纪要」。

---

## 五层地图（目录即职责）

```
brain-education/
├── foundations/   L1 理论底盘 —— 为什么这样理解大脑与五者
├── practice/      L2 因材施教 —— 孩子怎么带、怎么学、亲子怎么说
├── training/      L3 能力训练 —— 练什么、怎么验、异常怎么办
├── delivery/      L4 交付体系 —— 框架标准 + 护航 SOP
├── frontline/     L5 对外弹药 —— 招生、金句、案例、产品、科技
├── internal/      内部专用 —— 组织管理、智能体边界
├── meta/          溯源索引 —— 原始资料、章节映射
└── _templates/    扩写模板 —— 后续投喂用
```

| 层 | 目录 | 回答的问题 | 主要文件 |
|----|------|------------|----------|
| **L1** | foundations/（分层导航 README（本批未收录）） | 大脑与五者的「为什么」 | [theory](foundations/theory.md) · [talents](foundations/talents.md) |
| **L2** | practice/（分层导航 README（本批未收录）） | 这个孩子 / 这对父母怎么做 | [talents-application](practice/talents-application.md) · [learning-methods](practice/learning-methods.md) · parent-child/（亲子组合索引（本批未收录，仅收录已填格）） |
| **L3** | training/（分层导航 README（本批未收录）） | 练什么、怎么晋级、出事怎么办 | [methods](training/methods.md) · [safety](training/safety.md) |
| **L4** | delivery/（分层导航 README（本批未收录）） | 团队如何标准化交付 | [framework](delivery/training-system-framework.md) · [SOP](delivery/delivery-escort-sop.md) |
| **L5** | frontline/（分层导航 README（本批未收录）） | 招生转化与产品话术 | [sales](frontline/sales.md) · [quotes](frontline/quotes.md) · [cases](frontline/cases.md) · [products](frontline/products.md) · [technology](frontline/technology.md) |
| — | internal/（内部文档（另批隔离，本批未收录）） | 不对家长原文照念 | management（内部文档（另批隔离，本批未收录）） · agent-instruction（内部文档（另批隔离，本批未收录）） |
| — | [meta/](meta/sources.md) | 资料从哪来 | [sources](meta/sources.md) |

---

## 顾问速读路径

```
① foundations/theory     ← 为什么这样理解大脑
② foundations/talents    ← 五种人分别是谁
③ practice/talents-application ← 按孩子单型怎么带
④ practice/parent-child  ← 家长型×孩子型怎么说话
⑤ practice/learning-methods    ← 态度×方法系统
⑥ training/methods + safety    ← 练什么 / 异常处理
⑦ frontline/sales + quotes     ← 招生与口播
⑧ delivery/*                   ← 护航落地
```

### Cursor 引用（复制用）

- 理论：`@docs/brain-education/foundations/theory.md`
- 五者：`@docs/brain-education/foundations/talents.md`
- 孩子怎么带：`@docs/brain-education/practice/talents-application.md`
- 亲子宫格：`@docs/brain-education/practice/parent-child/`
- 学习方法：`@docs/brain-education/practice/learning-methods.md`
- 训练方法：`@docs/brain-education/training/methods.md`
- 安全手册：`@docs/brain-education/training/safety.md`
- 护航 SOP：`@docs/brain-education/delivery/delivery-escort-sop.md`
- 孩子不想来：`@docs/brain-education/frontline/sales.md`
- 金句：`@docs/brain-education/frontline/quotes.md`

---

## 单一真相源（改内容只改一处）

| 主题 | 全文落点 | 其它文件 |
|------|----------|----------|
| 五力展开 | [foundations/talents.md](foundations/talents.md) §二附 | theory §五 = 总框架 |
| 脑波 / 变聪明公式 | [foundations/theory.md](foundations/theory.md) §六 | technology = 设备形态 |
| 孩子单型怎么带 | [practice/talents-application.md](practice/talents-application.md) §五 | learning-methods §二 = 摘要 |
| 家长×孩子话术 | practice/parent-child/（见 `./practice/parent-child/`，本批未收录或路径待核） | sales = 跨组合通则 |
| 训练方法 / 九段 | [training/methods.md](training/methods.md) | — |
| 训练安全异常 | [training/safety.md](training/safety.md) | — |
| 修炼总诀用词 | [foundations/talents.md](foundations/talents.md) §四 | 应用篇对齐 |

---

## 本次整理做了什么（2026-08-28 架构）

| 动作 | 说明 |
|------|------|
| **按层分目录** | 理论 / 实践 / 训练 / 交付 / 对外 / 内部 / 溯源 |
| **拆分** | 原 `training.md` → `training/methods.md`（方法）+ `training/safety.md`（安全） |
| **合并入口** | 招生相关集中到 `frontline/`；交付两件套进 `delivery/` |
| **保留不硬并** | sales / quotes / cases 仍分文件（场景不同，便于 `@` 单文件） |
| **可扩展** | `_templates/` 提供亲子格、案例、产品补丁模板 |

旧扁平路径已失效；请改用上表新路径（姊妹库链接已同步更新）。

---

## 姊妹知识库

- 短剧：《天赋物语》（见 `../talent-drama/README.md`，本批未收录或路径待核）
- 财务：财务合规与多主体运营（见 `../finance-ops/README.md`，本批未收录或路径待核）

三套不要混读：教育本体 / 短剧演绎 / 经营账税。

---

## 背景与红线

- **主讲方**：张总（张宇老师）及其团队
- **资料性质**：区分「可执行标准」与「宣传数据」
- **转写误差**：「思者」常被误写为「死者/思哲」
- **交付红线**：禁止体罚；禁止具体提分承诺；医疗问题转医生
## 源材料路径

- **源材料**：本机 「源材料未随包公开」（未整包入库，勿外发）
- **已救回归档**：`meta/_raw/zhangyu-pack/`、`meta/transcript-screening-2026-08-28.md`（原误放在临时目录，已迁入）

---

## 口径裁定纪要（2026-08-28）

| # | 议题 | 裁定 |
|---|------|------|
| 1 | 「最不喜欢学」金句 | **思者**；核心在**监管（规矩+条件约束）**；学者用赏识 |
| 2 | 爱上学习链路 | **并存**：家长「快乐→成就→兴趣→成功」；交付「可见小成绩→信心→乐趣」 |
| 3 | 行者画像 | **双面**：封闭务实 / 好动偏赢；按副属性选用 |
| 4 | 内容重复 | **单一真相源**；别处摘要+链接 |
| 5 | α 脑波 | 统一 **8–13 Hz** |
| 6 | 死链 | 源材料注明本机 Downloads |
| 7 | 火箭营天数 | 两套会议说法并存；对外以**当期合同**为准 |

---

## 后续可完善清单

1. `practice/parent-child/` 其余 22 格全文（用模板填）
2. 日常作业 / 玩手机场景脚本
3. `training/` 一线课单元 SOP（从同事专业汇总继续抽）
4. `frontline/products.md` 第十一章按需精读
5. 高阶相生辩证另册（若有原文）
