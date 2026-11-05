"""第四层：角色卡加载。人设只来自数据文件，代码不再内置提示词/约束。"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

CARDS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class CharacterCard:
    key: str
    name: str
    tag: str = ""
    persona: str = ""
    voice: str = ""
    relations: str = ""
    voice_samples: tuple[str, ...] = ()
    appears_from: str = ""
    appears_until: str = ""
    in_channel: bool = True


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    return tuple(str(x) for x in value if x is not None and str(x).strip())


def _from_dict(data: dict[str, Any], *, fallback_key: str = "") -> CharacterCard | None:
    key = str(data.get("key") or fallback_key or "").strip()
    name = str(data.get("name") or "").strip()
    if not key or not name:
        return None
    return CharacterCard(
        key=key,
        name=name,
        tag=str(data.get("tag") or "").strip(),
        persona=str(data.get("persona") or "").strip(),
        voice=str(data.get("voice") or "").strip(),
        relations=str(data.get("relations") or "").strip(),
        voice_samples=_as_tuple(data.get("voice_samples")),
        appears_from=str(data.get("appears_from") or "").strip().upper(),
        appears_until=str(data.get("appears_until") or "").strip().upper(),
        in_channel=bool(data.get("in_channel", True)),
    )


@lru_cache(maxsize=1)
def all_cards() -> dict[str, CharacterCard]:
    found: dict[str, CharacterCard] = {}
    if yaml is None or not CARDS_DIR.is_dir():
        return found
    for path in sorted(CARDS_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            continue
        card = _from_dict(raw, fallback_key=path.stem)
        if card:
            found[card.key] = card
    return found


def get_card(key: str | None) -> CharacterCard | None:
    if not key:
        return None
    return all_cards().get(str(key).strip())


def clear_card_cache() -> None:
    all_cards.cache_clear()


def card_system_prompt(card: CharacterCard) -> str:
    """角色卡 → system。空字段不补默认约束句。"""
    bits: list[str] = []
    identity = card.name
    if card.tag:
        identity = f"{card.name}（{card.tag}）"
    bits.append(f"你是{identity}。")
    if card.persona:
        bits.append(card.persona)
    if card.voice:
        bits.append(f"说话：{card.voice}")
    if card.relations:
        bits.append(f"关系：{card.relations}")
    if card.voice_samples:
        bits.append("口吻参考：" + " / ".join(card.voice_samples[:4]))
    return "\n".join(bits).strip()
