"""LangGraph 约束学院讨论：先卡时间，再点名，再逐个开口。角色不互调。"""

from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.academy.characters import CHARACTERS, bot_id_for
from app.agents.academy.perception import leaks_future, time_box
from app.agents.academy.runtime import checkpointer, ensure_checkpointer, memory_store, thread_id


class SceneState(TypedDict, total=False):
    episode_id: str
    episode_title: str
    task: str
    child_talent: str
    mode: Literal["opening", "reply"]
    user_text: str
    prior: list
    last_who: str | None
    user_turns: int
    child_user_id: int
    mention: str
    quote: dict
    topic: str
    drama_notes: str
    affect: dict
    training_done: bool
    nudge_train: bool
    speakers: list
    index: int
    turns: list
    turn_ctx: dict


def bind_time(state: SceneState) -> SceneState:
    """时间节点只确认本集坐标，不生成台词。"""
    return {
        "episode_id": (state.get("episode_id") or "").upper(),
        "turns": list(state.get("turns") or []),
        "index": 0,
    }


def plan_cast(state: SceneState) -> SceneState:
    from app.agents.academy.harness import opening_order, wake_speakers
    from app.agents.academy.turn import prepare_turn

    if state.get("mode") == "reply":
        quote_who = (state.get("quote") or {}).get("who")
        speakers = wake_speakers(
            mention=state.get("mention"),
            quote_who=quote_who,
            last_who=state.get("last_who"),
        )
        ctx = prepare_turn(
            user_text=state.get("user_text") or "",
            episode_id=state.get("episode_id") or "",
            character_keys=speakers,
        )
        return {
            "speakers": speakers,
            "index": 0,
            "turn_ctx": {
                "raw_ask": ctx.raw_ask,
                "standalone_query": ctx.standalone_query,
                "skill": ctx.skill,
                "reasoning_mode": ctx.reasoning_mode,
                "synopsis": ctx.synopsis,
                "fact_default": ctx.fact_default,
                "facts_by_char": dict(ctx.facts_by_char),
            },
        }
    speakers = opening_order(state.get("child_talent"))
    if not speakers or speakers[-1] != "shanyu":
        speakers = [key for key in speakers if key != "shanyu"] + ["shanyu"]
    return {"speakers": speakers, "index": 0}


class BotState(TypedDict, total=False):
    character_key: str
    episode_id: str
    episode_title: str
    task: str
    child_talent: str
    child_user_id: int
    instruction: str
    drama_notes: str
    channel: list
    private: list
    memories: list
    scratch: dict
    line: dict
    time_box: str
    turn_index: int
    affect: dict
    turn_ctx: dict


def _turn_from_state(state: dict):
    from app.agents.academy.turn import TurnContext

    raw = state.get("turn_ctx") if isinstance(state.get("turn_ctx"), dict) else {}
    if not raw:
        return None
    return TurnContext(
        raw_ask=str(raw.get("raw_ask") or ""),
        standalone_query=str(raw.get("standalone_query") or ""),
        skill=str(raw.get("skill") or "answer"),
        reasoning_mode=str(raw.get("reasoning_mode") or "react"),
        synopsis=str(raw.get("synopsis") or ""),
        fact_default=str(raw.get("fact_default") or ""),
        facts_by_char=dict(raw.get("facts_by_char") or {}),
    )


def recall(state: BotState, config, *, store) -> BotState:
    bot_id = bot_id_for(state.get("character_key") or "")
    items = store.search((bot_id, "canon"), limit=6)
    texts = [str(item.value.get("text") or "") for item in items if item.value.get("text")]
    return {"memories": texts}


def _context_box(state: BotState) -> str:
    from app.agents.academy.skills import perceive
    from app.agents.academy.turn import turn_instruction
    from app.services.academy.bots import identity_box

    key = state.get("character_key") or ""
    episode_id = state.get("episode_id") or ""
    title = state.get("episode_title") or episode_id
    channel = list(state.get("channel") or [])
    turn = _turn_from_state(state)
    index = int(state.get("turn_index") or 0)
    if turn:
        skill_line = turn_instruction(turn, character_key=key, index=index)
        ground = turn.grounding(key)
    else:
        seen = perceive(
            key,
            episode_id=episode_id,
            episode_title=title,
            channel=channel,
            index=index,
            affect=state.get("affect"),
        )
        skill_line = seen.get("instruction") or ""
        ground = seen.get("grounding") or ""
    memories = "；".join(state.get("memories") or []) or "还没有新的自我感知"
    own = " / ".join(str(row.get("text") or "") for row in (state.get("private") or [])[-4:]) or "还没开口"
    box = (
        f"{time_box(key, episode_id, title)}\n{identity_box(key)}\n"
        f"感知技能：{skill_line}\n"
    )
    if ground:
        box += f"接地材料：{ground}\n"
    box += f"你记得的更新：{memories}\n你自己说过：{own}"
    notes = (state.get("drama_notes") or "").strip()
    if notes:
        box += (
            "\n短剧资料（调料不是剧本：借感觉，用自己的话；可结合常识举一个小例子。"
            "不要念原文，不要讲还没演到的事）：\n"
            + notes
        )
    return box


async def reason_node(state: BotState) -> BotState:
    """ReAct Thought/Action（模型）— 对应 LangGraph agent 的 reason 步。"""
    from app.agents.academy.harness import reason

    key = state.get("character_key") or ""
    box = _context_box(state)
    scratch = await reason(
        key,
        episode_title=state.get("episode_title") or state.get("episode_id") or "",
        task=state.get("task") or "",
        child_talent=state.get("child_talent") or "",
        prior=list(state.get("channel") or []),
        instruction=state.get("instruction") or "",
        time_box=box,
        episode_id=state.get("episode_id"),
    )
    return {"scratch": scratch, "time_box": box}


def observe_node(state: BotState) -> BotState:
    """ReAct Observation — 共享 turn 接地 + 资料 + 上一位同学。"""
    from app.agents.academy.harness import apply_observe, last_user_ask

    channel = list(state.get("channel") or [])
    turn = _turn_from_state(state)
    key = state.get("character_key") or ""
    ask = (turn.standalone_query if turn else "") or last_user_ask(channel)
    extra = turn.grounding(key) if turn else ""
    notes = state.get("drama_notes") or ""
    if extra:
        notes = f"{extra}\n{notes}".strip()
    scratch = apply_observe(
        state.get("scratch"),
        drama_notes=notes,
        channel=channel,
        user_ask=ask,
        episode_id=state.get("episode_id"),
        character_key=key,
    )
    return {"scratch": scratch}


async def say_node(state: BotState) -> BotState:
    """ReAct Final Answer — 只出口语台词到频道。"""
    from app.agents.academy.harness import _fallback, prior_said, say_line

    key = state.get("character_key") or ""
    episode_id = state.get("episode_id") or ""
    channel = list(state.get("channel") or [])
    line = await say_line(
        key,
        episode_title=state.get("episode_title") or episode_id,
        task=state.get("task") or "",
        child_talent=state.get("child_talent") or "",
        prior=channel,
        instruction=state.get("instruction") or "",
        scratch=state.get("scratch"),
        time_box=state.get("time_box") or _context_box(state),
        episode_id=episode_id,
    )
    if leaks_future(line["text"], episode_id):
        ask = next(
            (str(row.get("text") or "") for row in reversed(channel) if row.get("who") in ("me", "user")),
            "",
        )
        line = {
            "who": key,
            "text": _fallback(CHARACTERS[key], episode_id, avoid=prior_said(channel), user_ask=ask),
        }
    line = {**line, "bot_id": bot_id_for(key)}
    private = list(state.get("private") or []) + [line]
    return {"line": line, "private": private[-12:]}


def note(state: BotState, config, *, store) -> BotState:
    key = state.get("character_key") or ""
    store.put(
        (bot_id_for(key), "session", str(state.get("child_user_id") or 0), state.get("episode_id") or ""),
        "tail",
        {"lines": list(state.get("private") or [])[-8:]},
    )
    return {}


_BOTS: dict = {}
_BOTS_GENERATION = -1


def build_bot_graph(character_key: str):
    """单角色子图：recall → reason → observe → say → note。ReAct 是这个人的思考能力。"""
    del character_key  # 图结构相同，人设在 state 里
    graph = StateGraph(BotState)
    graph.add_node("recall", recall)
    graph.add_node("reason", reason_node)
    graph.add_node("observe", observe_node)
    graph.add_node("say", say_node)
    graph.add_node("note", note)
    graph.set_entry_point("recall")
    graph.add_edge("recall", "reason")
    graph.add_edge("reason", "observe")
    graph.add_edge("observe", "say")
    graph.add_edge("say", "note")
    graph.add_edge("note", END)
    return graph.compile(checkpointer=checkpointer(), store=memory_store())


def bot_graph(character_key: str):
    global _BOTS_GENERATION
    from app.agents.academy.runtime import checkpointer_generation

    gen = checkpointer_generation()
    if gen != _BOTS_GENERATION:
        _BOTS.clear()
        _BOTS_GENERATION = gen
    if character_key not in _BOTS:
        _BOTS[character_key] = build_bot_graph(character_key)
    return _BOTS[character_key]

def _hint(state: SceneState, key: str) -> str:
    from app.agents.academy.harness import is_greeting
    from app.agents.academy.turn import TurnContext, turn_instruction

    turn_raw = state.get("turn_ctx") if isinstance(state.get("turn_ctx"), dict) else {}
    if turn_raw:
        ctx = TurnContext(
            raw_ask=str(turn_raw.get("raw_ask") or ""),
            standalone_query=str(turn_raw.get("standalone_query") or ""),
            skill=str(turn_raw.get("skill") or "answer"),
            reasoning_mode=str(turn_raw.get("reasoning_mode") or "react"),
            synopsis=str(turn_raw.get("synopsis") or ""),
            fact_default=str(turn_raw.get("fact_default") or ""),
            facts_by_char=dict(turn_raw.get("facts_by_char") or {}),
        )
        base = turn_instruction(ctx, character_key=key, index=int(state.get("index") or 0))
    else:
        base = (
            "像同学微信。别报天赋名。短剧资料只借感觉；事实不够就用常识答准。"
        )
    bits = [base]
    greeting = is_greeting(state.get("user_text") or "")
    if state.get("topic") == "qa":
        bits.append("这是答题。不要讲题，不要给答案。用你的口气让孩子去学科答疑问。")
    mention_checkin = bool(state.get("nudge_train")) and int(state.get("index") or 0) == 0
    asked = "打卡" in (state.get("user_text") or "") or "修炼" in (state.get("user_text") or "")
    if mention_checkin:
        bits.append("这一轮可以随口半句今日修炼，不要展开。")
    elif not asked:
        bits.append("不要提今日修炼，不要提打卡。")
    from app.agents.academy.affect import speak_tone

    bits.append(speak_tone(key, state.get("affect")))
    if greeting:
        bits.append("孩子只是打招呼。先回问候，不要提站桩、膝盖或剧本。")
    quote = state.get("quote") or {}
    if state.get("mode") == "reply" and state.get("mention") == key:
        bits.append("孩子点名要你回。先回他这句，不要改题。")
    if state.get("mode") == "reply" and quote.get("who") == key:
        snippet = str(quote.get("text") or "")[:40]
        bits.append(f"孩子引用了你这句「{snippet}」。顺着往下说，别原样复读。")
    if key == "shanyu" and state.get("mode") != "reply":
        bits.append("导师收尾。回到这一集，口语一句。")
    return " ".join(bits)

def _channel(state: SceneState) -> list:
    prior = list(state.get("prior") or [])
    if state.get("mode") == "reply" and state.get("user_text"):
        line = {"who": "me", "text": state["user_text"]}
        if state.get("mention"):
            line["mention"] = state["mention"]
        if state.get("quote"):
            line["quote"] = state["quote"]
        prior = prior + [line]
    return prior + list(state.get("turns") or [])


async def speak_one(state: SceneState) -> SceneState:
    from app.agents.academy.harness import _fallback, prior_said

    await ensure_checkpointer()
    speakers = list(state.get("speakers") or [])
    index = int(state.get("index") or 0)
    if index >= len(speakers):
        return {}
    key = speakers[index]
    episode_id = state.get("episode_id") or ""
    from app.agents.academy.harness import is_greeting

    notes = state.get("drama_notes")
    if is_greeting(state.get("user_text") or ""):
        notes = ""
    elif notes is None:
        from app.agents.academy.kb import drama_notes

        names = [CHARACTERS[item].name for item in speakers if item in CHARACTERS]
        notes = await drama_notes(
            names=names,
            episode_id=episode_id,
            episode_title=state.get("episode_title") or episode_id,
            user_text=state.get("user_text") or "",
        )
    try:
        result = await bot_graph(key).ainvoke(
            {
                "character_key": key,
                "episode_id": episode_id,
                "episode_title": state.get("episode_title") or episode_id,
                "task": state.get("task") or "",
                "child_talent": state.get("child_talent") or "",
                "child_user_id": int(state.get("child_user_id") or 0),
                "instruction": _hint(state, key),
                "drama_notes": notes,
                "channel": _channel(state),
                "turn_index": index,
                "affect": state.get("affect") or {},
                "turn_ctx": state.get("turn_ctx") or {},
            },
            {"configurable": {"thread_id": thread_id(state.get("child_user_id"), episode_id, key)}},
        )
        line = result.get("line") or {
            "who": key,
            "text": _fallback(
                CHARACTERS[key],
                episode_id,
                avoid=prior_said(_channel(state)),
                user_ask=state.get("user_text") or "",
            ),
            "bot_id": bot_id_for(key),
        }
    except Exception:
        import logging

        from app.agents.academy.runtime import reset_checkpointer

        logging.getLogger(__name__).exception("角色 %s 这一轮失败，改用本集台词", key)
        reset_checkpointer()
        line = {
            "who": key,
            "text": _fallback(
                CHARACTERS[key],
                episode_id,
                avoid=prior_said(_channel(state)),
                user_ask=state.get("user_text") or "",
            ),
            "bot_id": bot_id_for(key),
        }
    quote = state.get("quote") or {}
    if quote.get("text") and (key == state.get("mention") or key == quote.get("who")):
        line = {**line, "quote": {"who": quote.get("who"), "text": quote.get("text")}}
    turns = list(state.get("turns") or []) + [line]
    return {"turns": turns, "index": index + 1, "drama_notes": notes or ""}

def _continue(state: SceneState) -> str:
    speakers = state.get("speakers") or []
    if int(state.get("index") or 0) < len(speakers):
        return "speak"
    return "end"


def build_scene_graph():
    graph = StateGraph(SceneState)
    graph.add_node("bind_time", bind_time)
    graph.add_node("plan", plan_cast)
    graph.add_node("speak", speak_one)
    graph.set_entry_point("bind_time")
    graph.add_edge("bind_time", "plan")
    graph.add_edge("plan", "speak")
    graph.add_conditional_edges("speak", _continue, {"speak": "speak", "end": END})
    return graph.compile()


_COMPILED = None


def scene_graph():
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = build_scene_graph()
    return _COMPILED


async def run_scene(state: SceneState) -> list[dict]:
    result = await scene_graph().ainvoke(state)
    return list(result.get("turns") or [])
