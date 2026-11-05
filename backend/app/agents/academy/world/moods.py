"""跨集情绪轻量读取。第三阶段：讨论注入「刚看完这集时的心情」。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

WORLD_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def _all_moods() -> dict[str, dict[str, dict[str, str]]]:
    path = WORLD_DIR / "moods.yaml"
    if yaml is None or not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, dict[str, str]]] = {}
    for eid, block in raw.items():
        if not isinstance(block, dict):
            continue
        chars: dict[str, dict[str, str]] = {}
        for key, row in block.items():
            if isinstance(row, dict):
                chars[str(key)] = {
                    "mood": str(row.get("mood") or "").strip(),
                    "note": str(row.get("note") or "").strip(),
                }
            elif isinstance(row, str) and row.strip():
                chars[str(key)] = {"mood": row.strip(), "note": ""}
        if chars:
            out[str(eid).strip().upper()] = chars
    return out


def clear_mood_cache() -> None:
    _all_moods.cache_clear()


def character_mood(character_key: str, episode_id: str | None) -> str:
    """该角色在本集刚结束时的情绪一行；无配置则空。"""
    key = (character_key or "").strip()
    eid = (episode_id or "").strip().upper()
    if not key or not eid:
        return ""
    row = _all_moods().get(eid, {}).get(key) or {}
    mood = row.get("mood") or ""
    note = row.get("note") or ""
    if not mood and not note:
        return ""
    if mood and note:
        return f"这一集刚结束时你的心情：{mood}。{note}"
    if mood:
        return f"这一集刚结束时你的心情：{mood}。"
    return note
