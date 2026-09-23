"""一轮讨论准备 — 对齐 D:\\11 的 prepare_turn：先理解再答，多人共用。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.agents.academy.harness import detect_intent, is_greeting, route_topic
from app.agents.academy.packs import pack_fact_seed, pack_synopsis


_SUMMARY = re.compile(r"总结|概括|剧情|讲讲|讲一下|这一集|发生了什么|讲了什么")
_HISTORY = re.compile(
    r"种姓|科举|黄巢|称帝|皇帝|大齐|历史|为什么|为啥|当上|有没有|吗|诗|黄金甲|榜|大旱"
)
_ORAL = re.compile(r"^(那个|就是|嗯+|啊+|呃+|请问|我想问一下|我想问|帮我|你们能帮我)")
# 「谁跟我一组」是找人，不是问怎么练
_INVITE = re.compile(r"谁跟我|跟我一组|一起站|一起练|组队|有人陪|谁陪|拉我一组|谁来")


def is_invite(ask: str) -> bool:
    return bool(_INVITE.search((ask or "").strip()))


@dataclass
class TurnContext:
    """本轮共享上下文：谁开口另算，每个 agent 的 ReAct 都读这份。"""

    raw_ask: str
    standalone_query: str
    skill: str
    reasoning_mode: str  # direct | react
    synopsis: str = ""
    fact_default: str = ""
    facts_by_char: dict[str, str] = field(default_factory=dict)
    topic_shift: bool = False

    def fact_for(self, character_key: str) -> str:
        return (self.facts_by_char.get(character_key) or self.fact_default or "").strip()

    def grounding(self, character_key: str = "") -> str:
        bits: list[str] = []
        fact = self.fact_for(character_key)
        if fact:
            bits.append(f"要点：{fact}")
        elif self.skill == "summary" and self.synopsis:
            bits.append(f"本集梗概：{self.synopsis}")
        return "；".join(bits)


def _standalone(raw: str) -> str:
    text = (raw or "").strip()
    text = _ORAL.sub("", text).strip(" ，,。.!！?？")
    return text or (raw or "").strip()


def _pick_skill(ask: str) -> str:
    if is_greeting(ask):
        return "greet"
    if _SUMMARY.search(ask):
        return "summary"
    if route_topic(ask) == "qa":
        return "redirect_qa"
    intent = detect_intent(ask)
    if intent == "feel":
        return "comfort"
    if intent == "train":
        return "train"
    return "answer"


def _reasoning_mode(skill: str, ask: str) -> str:
    """对齐 D11：寒暄直接回；事实/历史/总结走 ReAct（先接地再出话）。"""
    if skill in ("greet", "redirect_qa"):
        return "direct"
    if skill in ("summary", "answer") or _HISTORY.search(ask or ""):
        return "react"
    return "react"


def prepare_turn(
    *,
    user_text: str,
    episode_id: str,
    character_keys: list[str] | None = None,
) -> TurnContext:
    """用户开口后调用一次；本轮所有被唤醒的角色共用。"""
    raw = (user_text or "").strip()
    ask = _standalone(raw)
    skill = _pick_skill(ask or raw)
    synopsis = pack_synopsis(episode_id) if skill in ("summary", "answer") else ""
    facts: dict[str, str] = {}
    default = ""
    if skill == "answer":
        default = pack_fact_seed(episode_id, ask or raw, "")
        for key in character_keys or []:
            seeded = pack_fact_seed(episode_id, ask or raw, key)
            if seeded:
                facts[key] = seeded
                if not default:
                    default = seeded
    return TurnContext(
        raw_ask=raw,
        standalone_query=ask or raw,
        skill=skill,
        reasoning_mode=_reasoning_mode(skill, ask or raw),
        synopsis=synopsis or pack_synopsis(episode_id),
        fact_default=default,
        facts_by_char=facts,
        topic_shift=False,
    )


def turn_instruction(ctx: TurnContext, *, character_key: str = "", index: int = 0) -> str:
    """写进 reason/say 的共享指令（类似 D11 skill policy + 接地）。"""
    ask = ctx.standalone_query or ctx.raw_ask
    skill = ctx.skill
    fact = ctx.fact_for(character_key)
    synopsis = (ctx.synopsis or "").strip()
    lead = index == 0
    if skill == "greet":
        body = "感知：打招呼。先回问候，不要提剧情或训练。"
    elif skill == "summary":
        body = (
            "感知：要总结这一集。"
            f"用口语概括，禁止改答别的题。梗概：{synopsis or '只讲本集见过的。'}"
        )
    elif skill == "redirect_qa":
        body = "感知：学科题。不要讲题、不要给答案，让对方去学科答疑。"
    elif skill == "comfort":
        body = "感知：情绪低。先接住，再可轻轻贴本集。"
    elif skill == "train":
        if is_invite(ask):
            body = (
                f"感知：孩子在找人组队——「{ask}」。"
                "你是频道里的真人同学，正面表态：跟不跟、算不算你一个。"
                "用自己的口气应邀即可。禁止讲站桩要领、禁止说明书腔、禁止『我听着』、禁止改答别的题。"
            )
        else:
            body = "感知：问训练。用做过的那一下接，不要说明书腔。"
    else:
        if fact:
            body = (
                f"感知：事实/历史题。必须正面答「{ask}」。"
                f"先用常识说准，可用要点：{fact}。禁止改题、禁止背别的样例。"
            )
        else:
            body = (
                f"感知：要答「{ask}」。没有现成要点也要用常识正面答，"
                "禁止拿别的题或样例硬顶。"
            )
    if ctx.reasoning_mode == "react":
        body += " 你用 ReAct：先 Thought/Action，再根据 Observation 出口语。"
    else:
        body += " 直接一句口语即可。"
    if lead:
        body += " 你先开口，说完整。"
    else:
        if skill == "train" and is_invite(ask):
            body += " 你再表态：补一句也算你一个，或轻轻抬杠，不要复读上一句。"
        else:
            body += " 你接话：补半句或同感，不要重复上一句，不要另开新题。"
    return f"孩子原话：{ctx.raw_ask}\n独立问句：{ask}\n{body}"
