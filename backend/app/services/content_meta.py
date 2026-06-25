"""content_item 元数据解析 — OSS 系列标签、技能、时长估算"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import ContentItem

SKILL_PATTERNS = (
    "影像追忆",
    "扫描速记",
    "极速学习",
    "极速运算",
    "精力恢复",
    "数学奥秘",
    "文科奥秘",
    "理科奥秘",
    "英语奥秘",
    "高效作业",
    "超能力",
    "专注力",
)

SERIES_FROM_URL = (
    ("xuekeaomi", "xuekeaomi"),
    ("chaonengli", "chaonengli"),
    ("zhuanzhuli", "zhuanzhuli"),
    ("chaonaoaomi", "chaonaoaomi"),
)


def skill_from_title(title: str | None) -> str:
    if not title:
        return "训练"
    for skill in SKILL_PATTERNS:
        if skill in title:
            return skill
    return "训练"


def series_from_url(url: str | None) -> str:
    if not url:
        return "chaonaoaomi"
    lower = url.lower()
    for token, name in SERIES_FROM_URL:
        if token in lower:
            return name
    return "chaonaoaomi"


def parse_item_meta(item: ContentItem) -> dict:
    if item.instructions:
        try:
            data = json.loads(item.instructions)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {
        "series": series_from_url(item.play_url),
        "skill": skill_from_title(item.lesson_title),
    }


def estimate_duration_min(item: ContentItem) -> int:
    if item.duration_min and item.duration_min > 0:
        return int(item.duration_min)
    meta = parse_item_meta(item)
    if meta.get("duration_min"):
        return int(meta["duration_min"])
    size = int(meta.get("file_size_bytes") or 0)
    if size > 0:
        # MP3 体积粗算：约 1MB ≈ 1 分钟
        return max(5, min(30, round(size / (1024 * 1024))))
    return 12


def build_instructions_meta(row: dict, *, play_url: str | None = None) -> str:
    url = play_url or row.get("play_url") or ""
    meta = {
        "series": row.get("series") or series_from_url(url),
        "skill": row.get("skill") or skill_from_title(row.get("lesson_title") or row.get("file_name")),
        "stage": row.get("stage"),
        "part": row.get("part"),
        "oss_key": row.get("oss_key"),
        "file_size_bytes": row.get("file_size_bytes"),
    }
    return json.dumps({k: v for k, v in meta.items() if v is not None}, ensure_ascii=False)


def item_instruction(block: str, item_type: str) -> str:
    return json.dumps({"block": block, "item_type": item_type}, ensure_ascii=False)


def parse_item_instruction(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def is_json_instruction(raw: str | None) -> bool:
    if not raw:
        return False
    return raw.strip().startswith("{")
