# 文档规范化报告（步骤 4 · Document Normalization）

> 日期：2026-08-31
> 依据：[文档预处理规范](../文档预处理规范.md) 步骤 4
> 输入：`staging/cleaned/`
> 输出：`staging/normalized/`

## 摘要

| 项 | 数量 |
|----|------|
| 处理文件 | 20 |
| 内容有变更 | 5 |
| 链接改写次数 | 44 |
| 标题跳级文件 | 0 |
| 缺少 H1 | 0 |

## 已执行规则

1. 以 `cleaned/` 为输入，写出 `normalized/`（扁平路径保持）
2. 标题结构巡检（H1 存在性、跳级）；本批无自动改标题层级（结构已完整）
3. 正文无序列表行首 `*`/`+` → `-`（跳过代码块）
4. 指向本批未收录目标的 Markdown 链接 → 改为括号说明（模板/子 README/internal/raw/规范）
5. 指向不在 cleaned 内的路径 → 改为「本批未收录或路径待核」说明

## 标题巡检

- 全部文件均有 H1。
- 未发现标题跳级（H1→H3 等）。

## 链接改写明细

| 文件 | 类型 | 原 URL | 说明 |
|------|------|--------|------|
| `frontline/quotes.md` | excluded_target | `../practice/parent-child/README.md` | 亲子组合索引（本批未收录，仅收录已填格） |
| `frontline/sales.md` | excluded_target | `../practice/parent-child/README.md` | 亲子组合索引（本批未收录，仅收录已填格） |
| `frontline/sales.md` | excluded_target | `../practice/parent-child/README.md` | 亲子组合索引（本批未收录，仅收录已填格） |
| `frontline/sales.md` | excluded_target | `../internal/agent-instruction.md` | 内部文档（另批隔离，本批未收录） |
| `meta/sources.md` | excluded_target | `./_raw/zhangyu-pack/` | 原始归档（另批隔离，本批未收录） |
| `meta/sources.md` | url_normalize | `./transcript-screening-2026-08-28.md` | transcript-screening-2026-08-28.md |
| `practice/talents-application.md` | excluded_target | `parent-child/README.md` | 亲子组合索引（本批未收录，仅收录已填格） |
| `practice/talents-application.md` | excluded_target | `parent-child/README.md` | 亲子组合索引（本批未收录，仅收录已填格） |
| `practice/talents-application.md` | excluded_target | `parent-child/README.md` | 亲子组合索引（本批未收录，仅收录已填格） |
| `README.md` | excluded_target | `../文档预处理规范.md` | 文档预处理规范（仓库流程文档，非知识正文） |
| `README.md` | excluded_target | `./_templates/README.md` | 扩写模板（本批未收录） |
| `README.md` | excluded_target | `./foundations/README.md` | 分层导航 README（本批未收录） |
| `README.md` | url_normalize | `./foundations/theory.md` | foundations/theory.md |
| `README.md` | url_normalize | `./foundations/talents.md` | foundations/talents.md |
| `README.md` | excluded_target | `./practice/README.md` | 分层导航 README（本批未收录） |
| `README.md` | url_normalize | `./practice/talents-application.md` | practice/talents-application.md |
| `README.md` | url_normalize | `./practice/learning-methods.md` | practice/learning-methods.md |
| `README.md` | excluded_target | `./practice/parent-child/README.md` | 亲子组合索引（本批未收录，仅收录已填格） |
| `README.md` | excluded_target | `./training/README.md` | 分层导航 README（本批未收录） |
| `README.md` | url_normalize | `./training/methods.md` | training/methods.md |
| `README.md` | url_normalize | `./training/safety.md` | training/safety.md |
| `README.md` | excluded_target | `./delivery/README.md` | 分层导航 README（本批未收录） |
| `README.md` | url_normalize | `./delivery/training-system-framework.md` | delivery/training-system-framework.md |
| `README.md` | url_normalize | `./delivery/delivery-escort-sop.md` | delivery/delivery-escort-sop.md |
| `README.md` | excluded_target | `./frontline/README.md` | 分层导航 README（本批未收录） |
| `README.md` | url_normalize | `./frontline/sales.md` | frontline/sales.md |
| `README.md` | url_normalize | `./frontline/quotes.md` | frontline/quotes.md |
| `README.md` | url_normalize | `./frontline/cases.md` | frontline/cases.md |
| `README.md` | url_normalize | `./frontline/products.md` | frontline/products.md |
| `README.md` | url_normalize | `./frontline/technology.md` | frontline/technology.md |
| `README.md` | excluded_target | `./internal/README.md` | 内部文档（另批隔离，本批未收录） |
| `README.md` | excluded_target | `./internal/management.md` | 内部文档（另批隔离，本批未收录） |
| `README.md` | excluded_target | `./internal/agent-instruction.md` | 内部文档（另批隔离，本批未收录） |
| `README.md` | url_normalize | `./meta/sources.md` | meta/sources.md |
| `README.md` | url_normalize | `./meta/sources.md` | meta/sources.md |
| `README.md` | url_normalize | `./foundations/talents.md` | foundations/talents.md |
| `README.md` | url_normalize | `./foundations/theory.md` | foundations/theory.md |
| `README.md` | url_normalize | `./practice/talents-application.md` | practice/talents-application.md |
| `README.md` | broken_or_oob | `./practice/parent-child/` | 目标不在本批 cleaned 内 |
| `README.md` | url_normalize | `./training/methods.md` | training/methods.md |
| `README.md` | url_normalize | `./training/safety.md` | training/safety.md |
| `README.md` | url_normalize | `./foundations/talents.md` | foundations/talents.md |
| `README.md` | broken_or_oob | `../talent-drama/README.md` | 目标不在本批 cleaned 内 |
| `README.md` | broken_or_oob | `../finance-ops/README.md` | 目标不在本批 cleaned 内 |

## 逐文件

| 文件 | 变更 | 列表归一 | 链接改写 | 标题数 |
|------|------|----------|----------|--------|
| `delivery/delivery-escort-sop.md` | 否 | 0 | 0 | 29 |
| `delivery/training-system-framework.md` | 否 | 0 | 0 | 58 |
| `foundations/talents.md` | 否 | 0 | 0 | 43 |
| `foundations/theory.md` | 否 | 0 | 0 | 68 |
| `frontline/cases.md` | 否 | 0 | 0 | 1 |
| `frontline/products.md` | 否 | 0 | 0 | 26 |
| `frontline/quotes.md` | 是 | 0 | 1 | 9 |
| `frontline/sales.md` | 是 | 0 | 3 | 11 |
| `frontline/technology.md` | 否 | 0 | 0 | 17 |
| `meta/sources.md` | 是 | 0 | 2 | 18 |
| `meta/transcript-screening-2026-08-28.md` | 否 | 0 | 0 | 5 |
| `practice/learning-methods.md` | 否 | 0 | 0 | 39 |
| `practice/parent-child/de-si.md` | 否 | 0 | 0 | 16 |
| `practice/parent-child/xue-si.md` | 否 | 0 | 0 | 17 |
| `practice/parent-child/ying-xing.md` | 否 | 0 | 0 | 15 |
| `practice/talents-application.md` | 是 | 0 | 3 | 40 |
| `README.md` | 是 | 0 | 35 | 11 |
| `training/examples/training-plan-winner-girl-10yo.md` | 否 | 0 | 0 | 65 |
| `training/methods.md` | 否 | 0 | 0 | 44 |
| `training/safety.md` | 否 | 0 | 0 | 26 |

## 下一步（步骤 5）

- 对 `staging/normalized/` 做术语归一（五者名、转写错字等）并产出 `glossary.md`
