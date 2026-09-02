# 脑科学教育知识包（Staging 交付）

> 导出日期：2026-09-01 · 规格版本：v1 (2026-08-31) · 质检：通过（自动6项 + 黄金问题24条）

## 包内结构

| 路径 | 内容 |
|------|------|
| `chunks/` | 280 个切好、带来源前缀的文本块（Markdown） |
| `metadata/` | 与 chunk 一一对应的 sidecar（YAML） |
| `glossary.md` | 术语表（五者/技能/误写纠正） |
| `canon.md` | 权威口径（口径裁定 + 交付红线，高优先级独立块） |
| `manifest.json` | 语料清单（层/类型/排除/版本/处理日期） |
| `qa-golden.md` | 黄金问题集 + 期望命中说明（人工验收用） |
| `excluded.md` | 未纳入文件及原因 |
| `SPEC.md` | 本文档预处理规范副本 |

## 接手方工作

向量化 / Embedding、建索引、平台入库、检索与业务对接由**接手方**完成（见 [SPEC.md](./SPEC.md) 第 1.2 节）。
入库建议：
- `canon.md`、`glossary.md` 作**高优先级独立块**
- `metadata/` 中 `risk_level=medical_hint` 的块（safety）按医疗边界处理；`verify_required=true` 的块（frontline）保留须核实标记
- `chunks/` 内前缀已含来源 + 合规标记，检索回答可直接引用

## 原始文档

- 源目录：`docs/brain-education/brain-education/`（只读，未随包）
- 预处理规范：`docs/brain-education/文档预处理规范.md`（副本见 SPEC.md）
