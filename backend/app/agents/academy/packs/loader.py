"""剧集包加载 — 一集一套 YAML，加集只加目录。"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore


PACKS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class EpisodePack:
    id: str
    title: str
    topic: str = ""
    task: str = ""
    duration_label: str = ""
    poster: str = ""
    oss_key: str = ""
    switchable: bool = False
    chips: tuple[str, ...] = ()
    # 第二层：讨论区配置
    time_point: str = ""
    characters_present: tuple[str, ...] = ()
    characters_absent: tuple[str, ...] = ()
    knowledge_cutoff: str = ""
    scene_context: str = ""
    topic_hints: tuple[str, ...] = ()
    # 遗留字段（UI / 弹幕）；不再做人设兜底台词
    sense: dict[str, str] = field(default_factory=dict)
    lines: dict[str, tuple[str, ...]] = field(default_factory=dict)
    danmaku: tuple[str, ...] = ()
    plot: dict[str, Any] = field(default_factory=dict)
    fit: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def channel_name(self) -> str:
        return f"{self.id} · {self.title}讨论组"


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(x) for x in value if x is not None and str(x).strip())


def _parse_lines(raw: Any) -> dict[str, tuple[str, ...]]:
    out: dict[str, tuple[str, ...]] = {}
    if not isinstance(raw, dict):
        return out
    for key, items in raw.items():
        out[str(key)] = _as_tuple(items)
    return out


def _parse_fit(raw: Any) -> dict[str, tuple[str, ...]]:
    if not isinstance(raw, dict):
        return {}
    return {
        "must_have": _as_tuple(raw.get("must_have")),
        "must_not_alone": _as_tuple(raw.get("must_not_alone")),
    }


def _from_dict(data: dict[str, Any]) -> EpisodePack:
    eid = str(data.get("id") or "").strip().upper()
    if not eid:
        raise ValueError("pack missing id")
    present = _as_tuple(data.get("characters_present"))
    absent = _as_tuple(data.get("characters_absent"))
    hints = _as_tuple(data.get("topic_hints")) or _as_tuple(data.get("chips"))
    cutoff = str(data.get("knowledge_cutoff") or eid).strip().upper()
    scene = str(data.get("scene_context") or "").strip()
    if not scene:
        plot = data.get("plot") if isinstance(data.get("plot"), dict) else {}
        scene = str((plot or {}).get("synopsis") or data.get("topic") or "").strip()
    return EpisodePack(
        id=eid,
        title=str(data.get("title") or eid),
        topic=str(data.get("topic") or ""),
        task=str(data.get("task") or ""),
        duration_label=str(data.get("duration_label") or ""),
        poster=str(data.get("poster") or ""),
        oss_key=str(data.get("oss_key") or "").strip(),
        switchable=bool(data.get("switchable")),
        chips=_as_tuple(data.get("chips")),
        time_point=str(data.get("time_point") or f"{eid}结束").strip(),
        characters_present=present,
        characters_absent=absent,
        knowledge_cutoff=cutoff,
        scene_context=scene,
        topic_hints=hints,
        sense={str(k): str(v) for k, v in (data.get("sense") or {}).items()},
        lines=_parse_lines(data.get("lines")),
        danmaku=_as_tuple(data.get("danmaku")),
        plot=dict(data.get("plot") or {}),
        fit=_parse_fit(data.get("fit")),
    )


def _read_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML required to load episode packs")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid pack: {path}")
    return data


@lru_cache(maxsize=1)
def all_packs() -> dict[str, EpisodePack]:
    found: dict[str, EpisodePack] = {}
    if not PACKS_DIR.is_dir():
        return found
    for path in sorted(PACKS_DIR.glob("*/pack.yaml")):
        pack = _from_dict(_read_yaml(path))
        found[pack.id] = pack
    return found


def get_pack(episode_id: str | None) -> EpisodePack | None:
    if not episode_id:
        return None
    return all_packs().get(str(episode_id).strip().upper())


def switchable_ids() -> tuple[str, ...]:
    return tuple(p.id for p in all_packs().values() if p.switchable)


def pack_sense(episode_id: str) -> dict[str, str]:
    pack = get_pack(episode_id)
    return dict(pack.sense) if pack else {}


def pack_lines(episode_id: str, character_key: str) -> tuple[str, ...]:
    pack = get_pack(episode_id)
    if not pack:
        return ()
    return pack.lines.get(character_key, ())


def pack_fit(episode_id: str) -> dict[str, tuple[str, ...]]:
    pack = get_pack(episode_id)
    return dict(pack.fit) if pack else {}


def pack_synopsis(episode_id: str | None) -> str:
    pack = get_pack(episode_id)
    if not pack or not isinstance(pack.plot, dict):
        return ""
    return str(pack.plot.get("synopsis") or "").strip()[:180]


def pack_fact_seed(
    episode_id: str | None,
    user_ask: str | None,
    character_key: str = "",
) -> str:
    """按用户问句匹配剧集包事实种子。对不上则返回空，禁止拿别的题顶上。"""
    pack = get_pack(episode_id)
    if not pack:
        return ""
    ask = (user_ask or "").strip()
    if not ask:
        return ""
    facts = pack.plot.get("facts") if isinstance(pack.plot, dict) else None
    if not isinstance(facts, list):
        return ""
    key = (character_key or "").strip()
    for row in facts:
        if not isinstance(row, dict):
            continue
        matches = row.get("match") or []
        if isinstance(matches, str):
            matches = [matches]
        if not any(str(m) and str(m) in ask for m in matches):
            continue
        by = row.get("by") if isinstance(row.get("by"), dict) else {}
        picked = (by.get(key) if key else None) or row.get("seed") or ""
        text = str(picked).strip()
        if text:
            return text[:80]
    return ""


def clear_pack_cache() -> None:
    all_packs.cache_clear()
