"""第三层：Scene Manager — 决定谁接话、几个角色回。"""

from __future__ import annotations

import random

from app.agents.academy.cards import get_card
from app.agents.academy.characters import CHARACTERS, KIDS, TALENT_CHAR
from app.agents.academy.packs import get_pack
from app.agents.academy.perception import SPECIAL_BOX, episode_no


def _is_special(episode_id: str) -> bool:
    raw = (episode_id or "").strip().upper()
    return raw in SPECIAL_BOX or raw.startswith("EH") or raw.startswith("ES")


def appears_in_episode(character_key: str, episode_id: str | None) -> bool:
    """角色卡 appears_from / appears_until：主线按集号，特辑只拦「别的特辑专属」。"""
    card = get_card(character_key)
    if not card:
        return True
    ep = (episode_id or "").strip().upper()
    if not ep:
        return True
    fr = (card.appears_from or "").strip().upper()
    until = (card.appears_until or "").strip().upper()

    if _is_special(ep):
        if fr.startswith("EH") or fr.startswith("ES"):
            return fr == ep
        if until.startswith("EH") or until.startswith("ES"):
            return until == ep or not until
        return True

    n = episode_no(ep)
    if fr:
        if fr.startswith("EH") or fr.startswith("ES"):
            return False
        if episode_no(fr) > n:
            return False
    if until and not (until.startswith("EH") or until.startswith("ES")):
        if episode_no(until) < n:
            return False
    return True


def present_keys(episode_id: str | None) -> list[str]:
    """本集在场角色；无配置则回落全员图鉴。尊重 appears_from/until。"""
    pack = get_pack(episode_id)
    if pack and pack.characters_present:
        keys = [key for key in pack.characters_present if key in CHARACTERS]
    else:
        keys = list(CHARACTERS.keys())
    return [key for key in keys if appears_in_episode(key, episode_id)]


def absent_keys(episode_id: str | None) -> set[str]:
    pack = get_pack(episode_id)
    if not pack:
        return set()
    return {key for key in pack.characters_absent if key}


def select_speakers(
    *,
    episode_id: str | None,
    mode: str,
    child_talent: str | None = None,
    mention: str | None = None,
    quote_who: str | None = None,
    last_who: str | None = None,
    n: int = 2,
) -> list[str]:
    """
    调度规则：
    - @ / 引用优先
    - 只从 characters_present 里抽，排除 absent
    - opening：天赋同学先开口，导师收尾（若导师在场）
    - reply：默认 2 人，尽量不连麦 last_who
    """
    present = [key for key in present_keys(episode_id) if key not in absent_keys(episode_id)]
    if not present:
        present = list(CHARACTERS.keys())

    if mode == "opening":
        # 开场只留「天赋同学 + 导师」两人，避免 4 次串行 LLM 把 open/sector 拖到 70s+
        kids = [key for key in present if key in KIDS]
        random.shuffle(kids)
        lead = TALENT_CHAR.get((child_talent or "").strip())
        kid: str | None = None
        if lead and lead in present:
            kid = lead
        else:
            for key in kids:
                kid = key
                break
            if kid is None and present:
                kid = next((key for key in present if key != "shanyu"), present[0])
        if "shanyu" in present:
            return ([kid] if kid and kid != "shanyu" else []) + ["shanyu"]
        return [kid] if kid else present[:1]

    speakers: list[str] = []
    if mention in present:
        speakers.append(mention)
    if quote_who in present and quote_who not in speakers:
        speakers.append(quote_who)
    pool = [key for key in present if key != last_who and key not in speakers] or [
        key for key in present if key not in speakers
    ]
    random.shuffle(pool)
    for key in pool:
        if len(speakers) >= n:
            break
        speakers.append(key)
    if len(speakers) < n:
        for key in present:
            if key not in speakers:
                speakers.append(key)
            if len(speakers) >= n:
                break
    return speakers[:n]
