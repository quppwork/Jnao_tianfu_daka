"""第一层：全局事件因果图（粗粒度按集切片）。防剧透真相源。"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

Knowledge = Literal["lived", "heard", "unknown"]

WORLD_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class WorldEvent:
    id: str
    episode_id: str
    summary: str
    causes: tuple[str, ...] = ()
    knowledge: dict[str, Knowledge] = field(default_factory=dict)


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    return tuple(str(x) for x in value if x is not None and str(x).strip())


@lru_cache(maxsize=1)
def all_events() -> tuple[WorldEvent, ...]:
    path = WORLD_DIR / "events.yaml"
    if yaml is None or not path.is_file():
        return ()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = raw.get("events") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        return ()
    out: list[WorldEvent] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        eid = str(row.get("id") or "").strip()
        ep = str(row.get("episode_id") or "").strip().upper()
        summary = str(row.get("summary") or "").strip()
        if not eid or not ep or not summary:
            continue
        know_raw = row.get("knowledge") if isinstance(row.get("knowledge"), dict) else {}
        knowledge: dict[str, Knowledge] = {}
        for key, state in know_raw.items():
            token = str(state or "").strip().lower()
            if token in ("lived", "heard", "unknown"):
                knowledge[str(key)] = token  # type: ignore[assignment]
        out.append(
            WorldEvent(
                id=eid,
                episode_id=ep,
                summary=summary,
                causes=_as_tuple(row.get("causes")),
                knowledge=knowledge,
            )
        )
    return tuple(out)


def clear_world_cache() -> None:
    all_events.cache_clear()


def _is_special(episode_id: str) -> bool:
    raw = (episode_id or "").strip().upper()
    return raw.startswith("EH") or raw.startswith("ES")


def _episode_rank(episode_id: str) -> int:
    raw = (episode_id or "").strip().upper()
    if _is_special(raw):
        return -1
    digits = "".join(ch for ch in raw if ch.isdigit())
    return int(digits) if digits else 0


def events_upto(cutoff: str) -> list[WorldEvent]:
    """截至 knowledge_cutoff 的事件。特辑（EH*/ES*）只看本集，不与主线数字混排。"""
    raw = (cutoff or "").strip().upper()
    if not raw:
        return []
    if _is_special(raw):
        return [event for event in all_events() if event.episode_id == raw]
    limit = _episode_rank(raw)
    rows: list[WorldEvent] = []
    for event in all_events():
        if _is_special(event.episode_id):
            continue
        if _episode_rank(event.episode_id) <= limit:
            rows.append(event)
    return rows


def character_knowledge(
    character_key: str,
    *,
    cutoff: str,
    limit: int = 8,
) -> str:
    """该角色在截止集已知的事件摘要。unknown / 未标注 = 不可见。"""
    key = (character_key or "").strip()
    if not key or not cutoff:
        return ""
    bits: list[str] = []
    for event in events_upto(cutoff):
        state = event.knowledge.get(key, "unknown")
        if state == "unknown":
            continue
        label = "亲历" if state == "lived" else "听说"
        bits.append(f"[{label}] {event.summary}")
        if len(bits) >= limit:
            break
    return "\n".join(bits)
