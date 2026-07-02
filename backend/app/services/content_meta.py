"""content_item 元数据解析 — OSS 系列标签、技能、时长估算"""

from __future__ import annotations

import json
from io import BytesIO
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import ContentItem

SKILL_PATTERNS = (
    "超脑阅读",
    "超脑速读",
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
    "多元感知",
    "感知力",
    "超能力",
    "专注力",
)

SERIES_FROM_URL = (
    ("suzhiaomi", "suzhiaomi"),
    ("xuekeaomi", "xuekeaomi"),
    ("chaonengli", "chaonengli"),
    ("zhuanzhuli", "zhuanzhuli"),
    ("chaonaoaomi", "chaonaoaomi"),
    ("duoyuanganzhi", "duoyuanganzhi"),
)


def skill_from_title(title: str | None) -> str:
    if not title:
        return "训练"
    if "超脑速读" in title:
        return "超脑阅读"
    for skill in SKILL_PATTERNS:
        if skill in title:
            if skill == "超脑速读":
                return "超脑阅读"
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


def probe_audio_duration(url: str, timeout: int = 15) -> int | None:
    """用 mutagen 探测 OSS 音频真实时长（仅读 HTTP Range 头部，不下载完整文件）"""
    try:
        from urllib.parse import urlparse, urlunparse, quote
        from urllib.request import Request, urlopen

        from mutagen.mp3 import MP3

        p = urlparse(url)
        encoded = urlunparse((p.scheme, p.netloc, quote(p.path), p.params, p.query, p.fragment))
        req = Request(encoded, headers={"Range": "bytes=0-131072"})
        resp = urlopen(req, timeout=timeout)
        data = resp.read()
        audio = MP3(BytesIO(data))
        secs = audio.info.length
        if secs > 0:
            return max(1, round(secs / 60))
    except Exception:
        pass
    return None


def estimate_duration_min(item: ContentItem) -> int:
    if item.duration_min and item.duration_min > 0:
        return int(item.duration_min)
    meta = parse_item_meta(item)
    if meta.get("duration_min"):
        return int(meta["duration_min"])
    # 尝试 OSS 探测真实时长
    url = item.play_url or ""
    if url and ("oss-cn-beijing" in url or "aliyuncs.com" in url):
        from app.services.oss_client import sign_play_url
        signed = sign_play_url(url, expires=3600)
        if signed:
            probed = probe_audio_duration(signed)
            if probed:
                return probed
    # 探测失败 → 文件大小估算：约 1MB ≈ 1 分钟
    size = int(meta.get("file_size_bytes") or 0)
    if size > 0:
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


def content_display_title(content) -> str:
    """ContentItem 展示名"""
    if content.lesson_title and str(content.lesson_title).strip():
        return str(content.lesson_title).strip()
    meta = parse_item_meta(content)
    if meta.get("skill"):
        return str(meta["skill"])
    return "训练音频"


def resolve_training_item_title(item, content=None) -> str:
    """训练项展示名：lesson_title → skill → 默认"""
    if item.title and str(item.title).strip():
        return str(item.title).strip()
    if content and content.lesson_title and str(content.lesson_title).strip():
        return str(content.lesson_title).strip()
    inst = parse_item_instruction(
        item.instructions if is_json_instruction(item.instructions) else None
    )
    skill = inst.get("skill")
    if skill:
        return str(skill)
    if item.ability_type == "placeholder":
        return "占位训练"
    return "训练项"
