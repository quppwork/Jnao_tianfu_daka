# 数据清洗报告（步骤 3 · Data Cleaning）

> 清洗日期：2026-08-31
> 依据：[文档预处理规范](../文档预处理规范.md) 步骤 3
> 输入：[02-document-selection.json](./02-document-selection.json)
> 输出目录：`staging/cleaned/`（相对路径已去掉双层 `brain-education/`）

## 摘要

| 项 | 数量 |
|----|------|
| 处理文件 | 20 |
| 成功写出 | 20 |
| 内容有变更 | 20 |
| 发生路径替换 | 6 |
| 删除垃圾项 | 2 |

## 清洗规则（已执行）

1. 去 UTF-8 BOM；统一换行 LF
2. 连续 ≥3 空行压成 1 个空行；去掉行尾空白
3. 本机绝对路径 / `Downloads/...` / `/Users/...` → 「源材料未随包公开」类文案
4. 写出到 `staging/cleaned/`，**不覆盖源目录正文**
5. 删除源树 `__MACOSX/`、`.DS_Store`、正文树内 `._*`

## 垃圾清理

- 已删：`__MACOSX/ (整个目录)`
- 已删：`brain-education/.DS_Store`

## 路径替换命中

| 文件 | 次数 | 样例 |
|------|------|------|
| `brain-education/frontline/cases.md` | 1 | `Downloads/知识库原文件/视频转文字8.28/` |
| `brain-education/frontline/products.md` | 1 | `Downloads/知识库原文件/视频转文字8.28/` |
| `brain-education/frontline/quotes.md` | 1 | `Downloads/知识库原文件/` |
| `brain-education/meta/sources.md` | 3 | `/Users/tianlu/.Trash/生成文本/`; `Downloads/知识库原文件/张宇汇总资料包/`; `Downloads/知识库原文件/视频转 |
| `brain-education/meta/transcript-screening-2026-08-28.md` | 1 | `Downloads/知识库原文件/视频转文字8.28/` |
| `brain-education/README.md` | 1 | `Downloads/知识库原文件/` |

## 逐文件结果

| 源路径 | 清洗后 | BOM | CR | 空行折叠 | 行尾空白 | 路径替换 | 有变更 |
|--------|--------|-----|----|----------|----------|----------|--------|
| `brain-education/delivery/delivery-escort-sop.md` | `cleaned/delivery/delivery-escort-sop.md` | N | 0 | 0 | 60 | 0 | 是 |
| `brain-education/delivery/training-system-framework.md` | `cleaned/delivery/training-system-framework.md` | N | 0 | 65 | 6 | 0 | 是 |
| `brain-education/foundations/talents.md` | `cleaned/foundations/talents.md` | N | 0 | 0 | 74 | 0 | 是 |
| `brain-education/foundations/theory.md` | `cleaned/foundations/theory.md` | N | 0 | 0 | 99 | 0 | 是 |
| `brain-education/frontline/cases.md` | `cleaned/frontline/cases.md` | N | 0 | 0 | 2 | 1 | 是 |
| `brain-education/frontline/products.md` | `cleaned/frontline/products.md` | N | 0 | 15 | 13 | 1 | 是 |
| `brain-education/frontline/quotes.md` | `cleaned/frontline/quotes.md` | N | 0 | 0 | 4 | 1 | 是 |
| `brain-education/frontline/sales.md` | `cleaned/frontline/sales.md` | N | 0 | 0 | 24 | 0 | 是 |
| `brain-education/frontline/technology.md` | `cleaned/frontline/technology.md` | N | 0 | 1 | 6 | 0 | 是 |
| `brain-education/practice/learning-methods.md` | `cleaned/practice/learning-methods.md` | N | 0 | 0 | 58 | 0 | 是 |
| `brain-education/practice/parent-child/de-si.md` | `cleaned/practice/parent-child/de-si.md` | N | 0 | 0 | 14 | 0 | 是 |
| `brain-education/practice/parent-child/xue-si.md` | `cleaned/practice/parent-child/xue-si.md` | N | 0 | 0 | 20 | 0 | 是 |
| `brain-education/practice/parent-child/ying-xing.md` | `cleaned/practice/parent-child/ying-xing.md` | N | 0 | 0 | 13 | 0 | 是 |
| `brain-education/practice/talents-application.md` | `cleaned/practice/talents-application.md` | N | 0 | 0 | 53 | 0 | 是 |
| `brain-education/training/examples/training-plan-winner-girl-10yo.md` | `cleaned/training/examples/training-plan-winner-girl-10yo.md` | N | 0 | 0 | 6 | 0 | 是 |
| `brain-education/training/methods.md` | `cleaned/training/methods.md` | N | 0 | 0 | 65 | 0 | 是 |
| `brain-education/training/safety.md` | `cleaned/training/safety.md` | N | 0 | 0 | 39 | 0 | 是 |
| `brain-education/meta/sources.md` | `cleaned/meta/sources.md` | N | 0 | 0 | 21 | 3 | 是 |
| `brain-education/meta/transcript-screening-2026-08-28.md` | `cleaned/meta/transcript-screening-2026-08-28.md` | N | 0 | 0 | 5 | 1 | 是 |
| `brain-education/README.md` | `cleaned/README.md` | N | 0 | 0 | 13 | 1 | 是 |

## 下一步（步骤 4）

- 对 `staging/cleaned/` 做文档规范化（标题层级、表格、相对链接）
- 源目录正文仍保持只读；后续步骤继续基于 cleaned 副本
