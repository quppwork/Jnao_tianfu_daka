"""从百炼 ListIndexDocuments 刷新 kb_registry.yaml 的 tags（不镜像全文）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.core.logger import get_logger
from app.services.bailian.config import load_bailian_config
from app.services.bailian.list_documents import list_all_index_document_stems
from app.services.kb_registry import _REGISTRY_PATH, get_kb_registry

logger = get_logger("kb.registry_sync")

# 过短或无信息量的词不进 tags
_SKIP_STEMS = frozenset({
    "readme",
    "说明",
    "文档",
    "doc",
    "docx",
    "pdf",
    "新建",
    "副本",
})


def _stem_to_tags(stem: str) -> list[str]:
    s = (stem or "").strip()
    if not s or len(s) < 2:
        return []
    low = s.lower()
    if low in _SKIP_STEMS or s in _SKIP_STEMS:
        return []
    tags = [s]
    # 常见分隔：书名号、空格、下划线、横线
    for sep in ("——", "—", "-", "_", " ", "　", "【", "】", "（", "）", "(", ")"):
        if sep in s:
            for part in s.replace("【", " ").replace("】", " ").replace("（", " ").replace("）", " ").split():
                p = part.strip("-_— ")
                if len(p) >= 2 and p not in tags:
                    tags.append(p)
            break
    return tags[:8]


def merge_tags(existing: list[str], stems: list[str], *, max_tags: int = 80) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in existing + [x for s in stems for x in _stem_to_tags(s)]:
        t = (t or "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= max_tags:
            break
    return out


def sync_registry_tags_from_bailian(
    *,
    path: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """拉取两库已入库文件名，合并进 yaml tags；清掉 get_kb_registry 缓存。"""
    p = path or _REGISTRY_PATH
    cfg = load_bailian_config()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    sources = data.get("sources") or []
    report: dict[str, Any] = {"path": str(p), "dry_run": dry_run, "sources": {}}

    for raw in sources:
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("key") or "").strip()
        index_id = str(raw.get("index_id") or "").strip()
        # env 覆盖
        if key == "talent_doc" and cfg.index_id:
            index_id = cfg.index_id
        if key == "video_practice" and cfg.video_index_id:
            index_id = cfg.video_index_id
        if not key or not index_id:
            continue

        stems = list_all_index_document_stems(index_id=index_id, cfg=cfg)
        old_tags = [str(t) for t in (raw.get("tags") or []) if str(t).strip()]
        new_tags = merge_tags(old_tags, stems)
        added = [t for t in new_tags if t not in old_tags]
        report["sources"][key] = {
            "index_id": index_id,
            "doc_count": len(stems),
            "tags_before": len(old_tags),
            "tags_after": len(new_tags),
            "added": added[:30],
        }
        raw["tags"] = new_tags
        logger.info(
            "kb sync key=%s docs=%s tags %s→%s added=%s",
            key,
            len(stems),
            len(old_tags),
            len(new_tags),
            added[:10],
        )

    if not dry_run:
        p.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        get_kb_registry.cache_clear()

    return report
