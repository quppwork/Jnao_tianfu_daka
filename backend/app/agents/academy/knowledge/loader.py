"""从 packs/<EP>/knowledge.yaml 加载分集料包。缺文件则空料包（可扩展）。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from app.agents.academy.knowledge.types import EpisodeKnowledge
from app.agents.academy.packs.loader import PACKS_DIR

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    return tuple(str(x).strip() for x in value if x is not None and str(x).strip())


def _as_char_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, str] = {}
    for key, raw in value.items():
        text = str(raw or "").strip()
        if key and text:
            out[str(key).strip()] = text
    return out


def _as_facts(value: Any) -> tuple[dict, ...]:
    if not isinstance(value, list):
        return ()
    rows: list[dict] = []
    for item in value:
        if isinstance(item, dict):
            rows.append(dict(item))
    return tuple(rows)


def _from_dict(data: dict[str, Any], *, fallback_id: str) -> EpisodeKnowledge:
    eid = str(data.get("episode_id") or data.get("id") or fallback_id or "").strip().upper()
    return EpisodeKnowledge(
        episode_id=eid,
        title=str(data.get("title") or "").strip(),
        synopsis=str(data.get("synopsis") or "").strip(),
        beats=_as_tuple(data.get("beats")),
        character_beats=_as_char_map(data.get("character_beats")),
        can_talk=_as_tuple(data.get("can_talk")),
        cannot_know=_as_tuple(data.get("cannot_know")),
        spoilers_block=_as_tuple(data.get("spoilers_block")),
        facts=_as_facts(data.get("facts")),
    )


def _read_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML required to load episode knowledge")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"invalid knowledge yaml: {path}")
    return raw


@lru_cache(maxsize=1)
def all_knowledge() -> dict[str, EpisodeKnowledge]:
    found: dict[str, EpisodeKnowledge] = {}
    if not PACKS_DIR.is_dir():
        return found
    for path in sorted(PACKS_DIR.glob("*/knowledge.yaml")):
        eid = path.parent.name.strip().upper()
        know = _from_dict(_read_yaml(path), fallback_id=eid)
        if know.episode_id:
            found[know.episode_id] = know
    return found


def get_knowledge(episode_id: str | None) -> EpisodeKnowledge | None:
    if not episode_id:
        return None
    return all_knowledge().get(str(episode_id).strip().upper())


def clear_knowledge_cache() -> None:
    all_knowledge.cache_clear()
