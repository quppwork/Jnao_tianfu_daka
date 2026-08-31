# 语料筛选确认表（步骤 2 · Document Selection）

> 确认日期：2026-08-31
> 依据：[文档预处理规范](../文档预处理规范.md) 步骤 2
> 输入：[01-corpus-inventory.md](./01-corpus-inventory.md)
> **本表冻结本批范围**；后续步骤 3+ 仅处理「纳入」清单中的文件。

## 决策摘要

| 批次标签 | 含义 | 数量 |
|----------|------|------|
| `include_core` | 本批纳入 · 知识正文主路径 | 17 |
| `include_meta` | 本批纳入 · 索引/溯源元信息 | 3 |
| `hold_draft` | 本批不入 · 草稿占位 | 22 |
| `hold_isolate` | 另批 · internal / raw | 11 |
| `drop` | 排除 · 不进入任何本批处理 | 91 |

**本批合计纳入：20 个文件**（core 17 + meta 3）。

## 筛选原则（已执行）

1. 精修正文（foundations / practice 已填格 / training / delivery / frontline）→ `include_core`
2. 根 README、meta 溯源说明 → `include_meta`
3. 亲子占位格 → `hold_draft`
4. `internal/`、`meta/_raw/` → `hold_isolate`
5. `__MACOSX`、模板、子目录 README、预处理规范本身 → `drop`

## A. 本批纳入 · 知识正文（include_core）

### L1 foundations

| 相对路径 | 字节 | 决策说明 |
|----------|------|----------|
| `brain-education/foundations/talents.md` | 37214 | 纳入：精修正文 |
| `brain-education/foundations/theory.md` | 39456 | 纳入：精修正文 |

### L2 practice

| 相对路径 | 字节 | 决策说明 |
|----------|------|----------|
| `brain-education/practice/learning-methods.md` | 18682 | 纳入：精修正文 |
| `brain-education/practice/parent-child/de-si.md` | 5356 | 纳入：精修正文 |
| `brain-education/practice/parent-child/xue-si.md` | 6058 | 纳入：精修正文 |
| `brain-education/practice/parent-child/ying-xing.md` | 5175 | 纳入：精修正文 |
| `brain-education/practice/talents-application.md` | 24800 | 纳入：精修正文 |

### L3 training

| 相对路径 | 字节 | 决策说明 |
|----------|------|----------|
| `brain-education/training/examples/training-plan-winner-girl-10yo.md` | 21617 | 纳入：精修正文 |
| `brain-education/training/methods.md` | 22146 | 纳入：精修正文 |
| `brain-education/training/safety.md` | 12495 | 纳入：精修正文 |

### L4 delivery

| 相对路径 | 字节 | 决策说明 |
|----------|------|----------|
| `brain-education/delivery/delivery-escort-sop.md` | 9804 | 纳入：精修正文 |
| `brain-education/delivery/training-system-framework.md` | 25526 | 纳入：精修正文 |

### L5 frontline

| 相对路径 | 字节 | 决策说明 |
|----------|------|----------|
| `brain-education/frontline/cases.md` | 1870 | 纳入：案例索引；后续须核实/脱敏 |
| `brain-education/frontline/products.md` | 7273 | 纳入：精修正文 |
| `brain-education/frontline/quotes.md` | 4188 | 纳入：精修正文 |
| `brain-education/frontline/sales.md` | 5151 | 纳入：精修正文 |
| `brain-education/frontline/technology.md` | 6036 | 纳入：精修正文 |

## B. 本批纳入 · 元信息（include_meta）

| 相对路径 | 字节 | 决策说明 |
|----------|------|----------|
| `brain-education/meta/sources.md` | 7412 | 纳入：溯源元信息 |
| `brain-education/meta/transcript-screening-2026-08-28.md` | 2267 | 纳入：溯源元信息 |
| `brain-education/README.md` | 7189 | 纳入：总索引块 |

## C. 本批不入 · 草稿（hold_draft）

共 **22** 个（亲子占位格）。不进入清洗/分块。

<details><summary>展开路径列表</summary>

| 相对路径 | 字节 |
|----------|------|
| `brain-education/practice/parent-child/de-de.md` | 571 |
| `brain-education/practice/parent-child/de-xing.md` | 573 |
| `brain-education/practice/parent-child/de-xue.md` | 572 |
| `brain-education/practice/parent-child/de-ying.md` | 573 |
| `brain-education/practice/parent-child/si-de.md` | 571 |
| `brain-education/practice/parent-child/si-si.md` | 571 |
| `brain-education/practice/parent-child/si-xing.md` | 573 |
| `brain-education/practice/parent-child/si-xue.md` | 572 |
| `brain-education/practice/parent-child/si-ying.md` | 573 |
| `brain-education/practice/parent-child/xing-de.md` | 573 |
| `brain-education/practice/parent-child/xing-si.md` | 573 |
| `brain-education/practice/parent-child/xing-xing.md` | 575 |
| `brain-education/practice/parent-child/xing-xue.md` | 574 |
| `brain-education/practice/parent-child/xing-ying.md` | 575 |
| `brain-education/practice/parent-child/xue-de.md` | 572 |
| `brain-education/practice/parent-child/xue-xing.md` | 574 |
| `brain-education/practice/parent-child/xue-xue.md` | 573 |
| `brain-education/practice/parent-child/xue-ying.md` | 574 |
| `brain-education/practice/parent-child/ying-de.md` | 573 |
| `brain-education/practice/parent-child/ying-si.md` | 573 |
| `brain-education/practice/parent-child/ying-xue.md` | 574 |
| `brain-education/practice/parent-child/ying-ying.md` | 575 |

</details>

## D. 另批隔离（hold_isolate）

| 相对路径 | 分类 | 决策说明 |
|----------|------|----------|
| `brain-education/internal/agent-instruction.md` | 内部专用 | 另批：internal 或 raw |
| `brain-education/internal/management.md` | 内部专用 | 另批：internal 或 raw |
| `brain-education/internal/README.md` | 内部专用 | 另批：internal 或 raw |
| `brain-education/meta/_raw/zhangyu-pack/README.md` | 原始归档 | 另批：internal 或 raw |
| `brain-education/meta/_raw/zhangyu-pack/talent_stories_knowledge_base.md` | 原始归档 | 另批：internal 或 raw |
| `brain-education/meta/_raw/zhangyu-pack/瀛﹁€呭濡埫楁€濊€呭瀛恄瀹炴垬璇濇湳.md` | 原始归档 | 另批：internal 或 raw |
| `brain-education/meta/_raw/zhangyu-pack/瀛﹁€呭濡埫楁€濊€呭瀛恄鐪熷疄妗堜緥.md` | 原始归档 | 另批：internal 或 raw |
| `brain-education/meta/_raw/zhangyu-pack/鏅鸿兘浣撴寚浠ゆ眹鎬荤増_v1.0.md` | 原始归档 | 另批：internal 或 raw |
| `brain-education/meta/_raw/zhangyu-pack/閲戝彞姹囨€籣灏忓畤.md` | 原始归档 | 另批：internal 或 raw |
| `brain-education/meta/_raw/zhangyu-pack/閲戝彞鍚堥泦路妗堜緥涓庡闀垮挩璇㈢増.md` | 原始归档 | 另批：internal 或 raw |
| `brain-education/meta/_raw/zhangyu-pack/閿€鍞瘽鏈痏瀛╁瓙涓嶆兂鏉ョ殑涓夊ぇ鐞嗙敱.md` | 原始归档 | 另批：internal 或 raw |

## E. 排除（drop）

共 **91** 个（主要为 `__MACOSX` 垃圾、`_templates`、子 README、规范文件）。

| 排除原因分组 | 数量 |
|--------------|------|
| 解压/系统残留 | 79 |
| 子目录导航，建议并入 manifest | 6 |
| 写作模板 | 5 |
| 预处理规范本身，不入知识正文 | 1 |

## 确认结论

- [x] 本批 **core** 范围已冻结（上表 A）
- [x] 本批 **meta** 范围已冻结（上表 B）
- [x] draft / isolate / drop 不进入步骤 3 主清洗路径
- [ ] （可选）若需把 `cases.md` 整文件移出本批，在步骤 3 前人工改本表

## 下一步（步骤 3）

- 仅对 `include_core` + `include_meta` 共 **20** 个文件执行数据清洗
- 建议先物理清理源树中的 `__MACOSX` / `.DS_Store`（属 drop，可删垃圾不改正文）
