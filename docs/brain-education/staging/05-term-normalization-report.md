# 术语归一报告（步骤 5 · Term Normalization）

> 日期：2026-08-31
> 依据：[文档预处理规范](../文档预处理规范.md) 步骤 5
> 输入：`staging/normalized/`
> 输出：`staging/term_normalized/` + [glossary.md](./glossary.md)

## 摘要

| 项 | 数量 |
|----|------|
| 处理文件 | 20 |
| 发生替换的文件 | 0 |
| 替换规则命中合计 | 0 |

## 术语表

- 已生成：[glossary.md](./glossary.md)
- 同步副本：`term_normalized/glossary.md`

## 替换规则命中统计

本批 `normalized/` 正文中 **几乎已是标准写法**；仅「转写误差」说明中保留「死者/思哲」字样（有意不改）。仍产出 glossary，供后续入库与质检使用。

## 逐文件

| 文件 | 是否替换 | 明细 |
|------|----------|------|
| `delivery/delivery-escort-sop.md` | 否 | — |
| `delivery/training-system-framework.md` | 否 | — |
| `foundations/talents.md` | 否 | — |
| `foundations/theory.md` | 否 | — |
| `frontline/cases.md` | 否 | — |
| `frontline/products.md` | 否 | — |
| `frontline/quotes.md` | 否 | — |
| `frontline/sales.md` | 否 | — |
| `frontline/technology.md` | 否 | — |
| `meta/sources.md` | 否 | — |
| `meta/transcript-screening-2026-08-28.md` | 否 | — |
| `practice/learning-methods.md` | 否 | — |
| `practice/parent-child/de-si.md` | 否 | — |
| `practice/parent-child/xue-si.md` | 否 | — |
| `practice/parent-child/ying-xing.md` | 否 | — |
| `practice/talents-application.md` | 否 | — |
| `README.md` | 否 | — |
| `training/examples/training-plan-winner-girl-10yo.md` | 否 | — |
| `training/methods.md` | 否 | — |
| `training/safety.md` | 否 | — |

## 保护策略

- 含「转写误差 / 误写 / →」的行不替换「死者」「思哲」等字样，避免毁掉纠错说明。
- 代码块不替换。

## 下一步（步骤 6）

- 权威源与去重：按单一真相源表，标记 canonical / duplicate_of
