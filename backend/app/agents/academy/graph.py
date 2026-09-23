"""LangGraph 约束学院讨论：先卡时间，再点名，再逐个开口。角色不互调。"""

from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.academy.characters import CHARACTERS, bot_id_for
from app.agents.academy.perception import leaks_future
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
    from app.agents.academy.scene import select_speakers
    from app.agents.academy.turn import prepare_turn

    episode_id = state.get("episode_id") or ""
    if state.get("mode") == "reply":
        quote_who = (state.get("quote") or {}).get("who")
        speakers = select_speakers(
            episode_id=episode_id,
            mode="reply",
            mention=state.get("mention"),
            quote_who=quote_who,
            last_who=state.get("last_who"),
        )
        ctx = prepare_turn(
            user_text=state.get("user_text") or "",
            episode_id=episode_id,
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
    speakers = select_speakers(
        episode_id=episode_id,
        mode="opening",
        child_talent=state.get("child_talent"),
    )
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
    """已不再拼技能/幕感知；知识库走 drama_notes。"""
    del state
    return ""


async def reason_node(state: BotState) -> BotState:
    """取消 ReAct LLM；空 scratch 占位。"""
    return {"scratch": {"thought": "", "action": "answer", "observation": ""}, "time_box": ""}


def observe_node(state: BotState) -> BotState:
    """把知识库检索结果塞进 observation，供 say 使用。"""
    notes = (state.get("drama_notes") or "").strip()
    scratch = dict(state.get("scratch") or {})
    scratch["action"] = "answer"
    scratch["observation"] = notes
    return {"scratch": scratch}


async def say_node(state: BotState) -> BotState:
    """角色卡 + 认知笔记出话；失败或剧透则跳过该角色。"""
    from app.agents.academy.harness import say_line
    from app.agents.academy.turn import turn_instruction

    key = state.get("character_key") or ""
    episode_id = state.get("episode_id") or ""
    channel = list(state.get("channel") or [])
    notes = (state.get("drama_notes") or "").strip()
    ctx = _turn_from_state(state)
    instruction = ""
    if ctx:
        instruction = turn_instruction(
            ctx,
            character_key=key,
            index=int(state.get("turn_index") or 0),
        )
    line = await say_line(
        key,
        episode_title=state.get("episode_title") or episode_id,
        task=state.get("task") or "",
        child_talent=state.get("child_talent") or "",
        prior=channel,
        instruction=instruction,
        scratch=state.get("scratch"),
        time_box="",
        episode_id=episode_id,
        drama_notes=notes,
    )
    if not line:
        return {"line": {}, "private": list(state.get("private") or [])}
    if leaks_future(line["text"], episode_id):
        return {"line": {}, "private": list(state.get("private") or [])}
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
    """单角色：recall →（空 reason）→ 注入知识库 → say → note。"""
    del character_key
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
    """额外策略提示已停用；回答只靠人设 + 知识库。"""
    del state, key
    return ""

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
    await ensure_checkpointer()
    speakers = list(state.get("speakers") or [])
    index = int(state.get("index") or 0)
    if index >= len(speakers):
        return {}
    key = speakers[index]
    episode_id = state.get("episode_id") or ""
    from app.agents.academy.harness import is_greeting
    from app.agents.academy.kb import drama_notes
    from app.agents.academy.packs import get_pack

    pack = get_pack(episode_id)
    cutoff = (pack.knowledge_cutoff if pack else "") or episode_id
    notes = state.get("drama_notes")
    if is_greeting(state.get("user_text") or ""):
        notes = ""
    elif notes is None:
        names = [CHARACTERS[item].name for item in speakers if item in CHARACTERS]
        notes = await drama_notes(
            names=names,
            episode_id=episode_id,
            episode_title=state.get("episode_title") or episode_id,
            user_text=state.get("user_text") or "",
            character_key=key,
            knowledge_cutoff=cutoff,
        )
    else:
        # 已有共享 notes 时仍叠加本角色全局图认知
        from app.agents.academy.world import character_knowledge

        known = character_knowledge(key, cutoff=cutoff)
        if known:
            notes = f"{notes}\n{known}".strip() if notes else known

    line: dict = {}
    try:
        result = await bot_graph(key).ainvoke(
            {
                "character_key": key,
                "episode_id": episode_id,
                "episode_title": state.get("episode_title") or episode_id,
                "task": state.get("task") or "",
                "child_talent": state.get("child_talent") or "",
                "child_user_id": int(state.get("child_user_id") or 0),
                "instruction": "",
                "drama_notes": notes or "",
                "channel": _channel(state),
                "turn_index": index,
                "affect": state.get("affect") or {},
                "turn_ctx": state.get("turn_ctx") or {},
            },
            {"configurable": {"thread_id": thread_id(state.get("child_user_id"), episode_id, key)}},
        )
        raw = result.get("line") or {}
        if isinstance(raw, dict) and raw.get("text"):
            line = raw
    except Exception:
        import logging

        from app.agents.academy.runtime import reset_checkpointer

        logging.getLogger(__name__).exception("角色 %s 这一轮失败，跳过", key)
        reset_checkpointer()
        line = {}

    turns = list(state.get("turns") or [])
    if line.get("text"):
        quote = state.get("quote") or {}
        if quote.get("text") and (key == state.get("mention") or key == quote.get("who")):
            line = {**line, "quote": {"who": quote.get("who"), "text": quote.get("text")}}
        if "bot_id" not in line:
            line = {**line, "bot_id": bot_id_for(key)}
        turns = turns + [line]
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
