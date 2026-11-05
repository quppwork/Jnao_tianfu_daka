"""把 EpisodeKnowledge 编成可注入 prompt 的短文本（非台词模板）。"""

from __future__ import annotations

from app.agents.academy.knowledge.types import EpisodeKnowledge


def format_episode_notes(
    know: EpisodeKnowledge | None,
    *,
    character_key: str = "",
    max_chars: int = 700,
) -> str:
    if not know or know.empty:
        return ""
    bits: list[str] = []
    if know.synopsis:
        bits.append(f"本集梗概：{know.synopsis.strip()}")
    if know.beats:
        beats = "；".join(b.strip() for b in know.beats if b.strip())
        if beats:
            bits.append(f"情节节拍：{beats}")
    key = (character_key or "").strip()
    if key and know.character_beats.get(key):
        bits.append(f"你本集视角：{know.character_beats[key].strip()}")
    if know.can_talk:
        bits.append("可聊：" + "、".join(know.can_talk[:12]))
    if know.cannot_know:
        bits.append("本集未知/勿提：" + "、".join(know.cannot_know[:12]))
    text = "\n".join(bits).strip()
    return text[: max(0, max_chars)]


def character_perspective(know: EpisodeKnowledge | None, character_key: str) -> str:
    if not know or not character_key:
        return ""
    return (know.character_beats.get(character_key) or "").strip()


def knowledge_synopsis(know: EpisodeKnowledge | None, *, limit: int = 200) -> str:
    if not know:
        return ""
    return (know.synopsis or "").strip()[:limit]


def knowledge_fact_seed(
    know: EpisodeKnowledge | None,
    user_ask: str | None,
    character_key: str = "",
) -> str:
    """可选事实锚点：按 match 命中返回短 seed，不是台词。"""
    if not know or not know.facts:
        return ""
    ask = (user_ask or "").strip()
    if not ask:
        return ""
    key = (character_key or "").strip()
    for row in know.facts:
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


def boundary_line(know: EpisodeKnowledge | None) -> str:
    if not know:
        return ""
    parts: list[str] = []
    if know.can_talk:
        parts.append("围绕：" + "、".join(know.can_talk[:8]))
    if know.cannot_know:
        parts.append("勿提：" + "、".join(know.cannot_know[:8]))
    return "；".join(parts)
