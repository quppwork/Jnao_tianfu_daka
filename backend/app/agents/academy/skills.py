"""每个画中人的感知技能 — 薄封装，一轮细节见 turn.prepare_turn。"""

from __future__ import annotations

from app.agents.academy.characters import CHARACTERS
from app.agents.academy.harness import last_user_ask
from app.agents.academy.perception import time_box
from app.agents.academy.turn import TurnContext, prepare_turn, turn_instruction


def perceive(
    character_key: str,
    *,
    episode_id: str,
    episode_title: str,
    channel: list[dict] | None,
    index: int = 0,
    affect: dict | None = None,
    turn: TurnContext | None = None,
) -> dict:
    """不调模型。优先用本轮共享 TurnContext。"""
    ask = last_user_ask(channel)
    ctx = turn or prepare_turn(user_text=ask, episode_id=episode_id, character_keys=[character_key])
    char = CHARACTERS.get(character_key)
    return {
        "ask": ctx.raw_ask or ask,
        "standalone_query": ctx.standalone_query,
        "skill": ctx.skill,
        "reasoning_mode": ctx.reasoning_mode,
        "role": "lead" if index == 0 else "listen",
        "fact": ctx.fact_for(character_key),
        "synopsis": ctx.synopsis,
        "grounding": ctx.grounding(character_key),
        "sense": time_box(character_key, episode_id, episode_title),
        "name": char.name if char else character_key,
        "affect": affect or {},
        "instruction": turn_instruction(ctx, character_key=character_key, index=index),
    }


def skill_instruction(perceived: dict | None) -> str:
    row = perceived or {}
    if row.get("instruction"):
        return str(row["instruction"])
    ask = row.get("ask") or ""
    skill = row.get("skill") or "answer"
    fact = (row.get("fact") or "").strip()
    synopsis = (row.get("synopsis") or "").strip()
    if skill == "summary":
        return f"总结本集。梗概：{synopsis or '只讲本集。'} 孩子说：{ask}"
    if fact:
        return f"答「{ask}」。要点：{fact}"
    return f"正面答「{ask}」，禁止改题。"
