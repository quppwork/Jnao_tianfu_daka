# 未纳入文件清单（excluded）

> 依据：步骤2 语料筛选（`02-document-selection.json`）· 处理日期 2026-09-01

## 一、垃圾 / 系统文件（drop · 91 个）

`__MACOSX/`、`._*`、`.DS_Store` 等解压/系统残留，**直接删除**。
代表条目：`__MACOSX/._brain-education`、`__MACOSX/brain-education/._.DS_Store`、`.DS_Store` 等。

## 二、草稿 / 占位（hold_draft · 22 个）

仅标题无正文的占位（多为 parent-child 其余格），**不入本批**：
- `brain-education/practice/parent-child/de-de.md`
- `brain-education/practice/parent-child/de-xing.md`
- `brain-education/practice/parent-child/de-xue.md`
- `brain-education/practice/parent-child/de-ying.md`
- `brain-education/practice/parent-child/si-de.md`
- `brain-education/practice/parent-child/si-si.md`
- `brain-education/practice/parent-child/si-xing.md`
- `brain-education/practice/parent-child/si-xue.md`
- `brain-education/practice/parent-child/si-ying.md`
- `brain-education/practice/parent-child/xing-de.md`
- `brain-education/practice/parent-child/xing-si.md`
- `brain-education/practice/parent-child/xing-xing.md`
- `brain-education/practice/parent-child/xing-xue.md`
- `brain-education/practice/parent-child/xing-ying.md`
- `brain-education/practice/parent-child/xue-de.md`
- `brain-education/practice/parent-child/xue-xing.md`
- `brain-education/practice/parent-child/xue-xue.md`
- `brain-education/practice/parent-child/xue-ying.md`
- `brain-education/practice/parent-child/ying-de.md`
- `brain-education/practice/parent-child/ying-si.md`
- `brain-education/practice/parent-child/ying-xue.md`
- `brain-education/practice/parent-child/ying-ying.md`

## 三、内部隔离（hold_isolate · 11 个）

内部专用 / 原始归档，**另批隔离处理**，不与对外正文混切：
- `brain-education/internal/agent-instruction.md`
- `brain-education/internal/management.md`
- `brain-education/internal/README.md`
- `brain-education/meta/_raw/zhangyu-pack/README.md`
- `brain-education/meta/_raw/zhangyu-pack/talent_stories_knowledge_base.md`
- `brain-education/meta/_raw/zhangyu-pack/瀛﹁€呭濡埫楁€濊€呭瀛恄瀹炴垬璇濇湳.md`
- `brain-education/meta/_raw/zhangyu-pack/瀛﹁€呭濡埫楁€濊€呭瀛恄鐪熷疄妗堜緥.md`
- `brain-education/meta/_raw/zhangyu-pack/鏅鸿兘浣撴寚浠ゆ眹鎬荤増_v1.0.md`
- `brain-education/meta/_raw/zhangyu-pack/閲戝彞姹囨€籣灏忓畤.md`
- `brain-education/meta/_raw/zhangyu-pack/閲戝彞鍚堥泦路妗堜緥涓庡闀垮挩璇㈢増.md`
- `brain-education/meta/_raw/zhangyu-pack/閿€鍞瘽鏈痏瀛╁瓙涓嶆兂鏉ョ殑涓夊ぇ鐞嗙敱.md`

---
> 说明：以上三类均未进入本包；本包仅含 `manifest.json` 中 `total_chunks`（280 块）对应的语料。
