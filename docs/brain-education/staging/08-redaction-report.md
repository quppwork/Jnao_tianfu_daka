# 步骤8 脱敏与合规 处理报告

> 范围：`staging/aligned/` → `staging/redacted/`
> 依据：[08-probe-sensitive.md](./08-probe-sensitive.md)（66 命中）+ 补扫新发现（探查遗漏 4 处实名）
> 决策（用户确认）：**署名 = 正文泛化 + meta 留注记**；**效果数字 = 仅保留须核实标注（不删原文）**
> 规范：《文档预处理规范》步骤 8

## 一、总览

| 类别 | 命中数 | 处理 | 落点 |
|------|--------|------|------|
| 案例/学员实名 | 6 | **泛化为角色代号**（删除可识别身份） | `frontline/cases.md`、`frontline/products.md` |
| 团队署名（正文） | 7 | **泛化为角色**（创始人 / 主讲人 / 教学负责人） | `products`、`sales`、`quotes`、`README` |
| 团队署名（meta） | 9 | **保留原名 + 块头内部溯源注记** | `meta/sources.md` |
| 效果数字 / 升学承诺 | 18 | **不删**，保留既有「须核实 / 勿当承诺」横幅 | `cases`、`products` 等 |
| 医疗 / 心理术语 | 28 | **不删原文**；safety 加固定免责横幅；「处方」标教学类比 | `safety`、`learning-methods`、`talents-application` |
| 红线-禁止体罚 | 7 | 合规正向内容，保留 | — |
| 地域 | 2 | 省级粒度不足以定位个人，保留 | `safety`、`meta/sources` |
| **合计处理** | **16 处替换 + 2 处横幅 + 3 处类比注记** | | |

## 二、已脱敏（实名 → 角色代号）

| 文件 | 行 | 原 | 现 |
|------|----|----|----|
| `frontline/cases.md` | 20 | 郑××中考线 | **某中考学员线**（代号同步泛化，cases 内唯一引用） |
| `frontline/cases.md` | 23 | 甘明英孙女 | **某教育工作者孙女** |
| `frontline/cases.md` | 24 | 杨子琪妈妈 | **某全职陪读家长** |
| `frontline/products.md` | 71 | 学员连战 | **某学员**（探查遗漏，补扫发现） |

## 三、已泛化（正文署名 → 角色；meta 留注记）

### 正文（泛化）

| 文件 | 行 | 原 | 现 |
|------|----|----|----|
| `frontline/products.md` | 94 | 管理团：张总 + 核心班子 | **创始人** + 核心班子 |
| `frontline/products.md` | 95 | 播商学院：殷老师、李敏智老师主抓 | **教学负责人**主抓（探查遗漏） |
| `frontline/sales.md` | 28 | 张宇核心逻辑三条 | **主讲人**核心逻辑三条 |
| `frontline/quotes.md` | 11 | 精选自同事金句合集 / 汇总_小宇 / 大会版 | 精选自同事金句合集 / 大会版 |
| `README.md` | 7 | 同事张宇汇总资料包 | 同事汇总资料包 |
| `README.md` | 112 | 主讲方：张总（张宇老师）及其团队 | **创始人（主讲人）**及其团队 |
| `README.md` | 119 | `meta/_raw/zhangyu-pack/` | `meta/_raw/team-pack/`（归档路径中性化） |

### meta（保留 + 注记）

- `meta/sources.md`：块头新增**内部溯源注记横幅**，声明「保留真实人名与归档文件名，入库建议标记 internal 或排除于对外检索；正文知识库已做泛化处理」。
- 文件名中的 `甘明英 / 杨子琪 / 王艳`、署名 `张宇 / 小宇 / 张宇汇总`、路径 `_raw/zhangyu-pack/` 全部保留。

## 四、保留原文 + 合规标注

### 4.1 效果数字 / 升学承诺（18 处，不删）

保留依据：各文件已带双层保护，切块后可逐块继承：

- 文件级「须核实 / 非承诺」横幅：`cases.md`、`quotes.md`、`sales.md`、`products.md` 顶部均已有 `verify-required-banner`
- 行级「勿当承诺」列：`cases.md` 每条案例钩子自带（如「勿承诺 15 天+70」「勿当请假必超省第一」）
- `products.md` 天数/价目全部标注「以当期合同为准」

步骤 11 将对这些文件统一标 `verify_required: true`（见 §六标注表），确保切块后每个 chunk 带提醒。

### 4.2 医疗 / 心理术语（28 处，不删 + 免责）

- **`training/safety.md` 新增块头固定免责横幅**（非医疗诊断/治疗/处方；遇医疗与极端心理问题须咨询专业人士）。
- 「处方 ≈ 诊断→病理→处方」为**教学类比**，已加注记（3 处）：
  - `learning-methods.md` §0.6「处方总则」
  - `talents-application.md` §5.8「当场开处方」
  - `talents-application.md` §5.8 速查卡「4. 处方」
- 「幻视幻听 / 幻觉 / 布洛芬 / 感知幻觉」等术语为安全手册自身体系，保留原文。

### 4.3 红线-禁止体罚（7 处，保留）

全部为**合规正向陈述**（「交付红线：禁止体罚与人格羞辱」），非违规内容。

### 4.4 地域（2 处，保留）

`山西三年级`（书中案例，省级粒度）、`西安 / 杭州`（meta 中会议地点）——不足以定位个人。

## 五、残留核验

对 `redacted/` 全量扫描实名/署名关键词，**残留仅存在于 `meta/sources.md`**（已按决策留注记），正文零残留。

## 六、content_type / risk_level 标注表（供步骤 11 元数据消费）

| 文件 | doc_role | content_type | risk_level | verify_required |
|------|----------|--------------|------------|-----------------|
| README.md | index | index（总索引） | none | false |
| canon.md | — | canon | none | false |
| canonical-map.md | — | canon | none | false |
| glossary.md | glossary | glossary | none | false |
| foundations/theory.md | canonical | theory | none | false |
| foundations/talents.md | canonical | theory | none | false |
| practice/learning-methods.md | summary_of | sop | none | false |
| practice/talents-application.md | canonical | sop | none | false |
| practice/parent-child/de-si.md | canonical | sop | none | false |
| practice/parent-child/ying-xing.md | canonical | sop | none | false |
| practice/parent-child/xue-si.md | canonical | sop | none | false |
| training/methods.md | canonical | sop | none | false |
| training/safety.md | canonical | sop | **medical_hint** | false |
| training/examples/training-plan-winner-girl-10yo.md | unique | sop | none | false |
| delivery/training-system-framework.md | unique | sop | none | false |
| delivery/delivery-escort-sop.md | unique | sop | none | false |
| frontline/cases.md | unique | case | none | **true** |
| frontline/quotes.md | unique | sales | none | **true** |
| frontline/sales.md | unique | sales | none | **true** |
| frontline/products.md | unique | sales | none | **true** |
| frontline/technology.md | summary_of | theory | none | false |
| meta/sources.md | index | meta（溯源，internal 注记） | none | false |
| meta/transcript-screening-2026-08-28.md | index | meta（溯源，internal 注记） | none | false |

> 注：`content_type` 为规范建议字段枚举（theory | sop | sales | case | glossary | canon）上的扩展；`meta / index` 为本包溯源与导航文件专用。safety 标 `medical_hint` 供入库侧风险分级。

## 七、交接说明

- 后续步骤（9 切块 → 13 Staging）将基于 **`staging/redacted/`**。
- 处理脚本：`08-redact.py`（可重复执行，aligned → redacted 幂等替换）。
- 注意：`meta/sources.md` 含真实人名，若接手方将 meta 纳入对外检索，须按注记先行排除。
