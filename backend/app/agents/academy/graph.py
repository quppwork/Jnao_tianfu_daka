"""LangGraph 约束学院讨论：先卡时间，再点名，再逐个开口。角色不互调。"""

from __future__ import annotations

from typing import Literal, TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from app.agents.academy.characters import CHARACTERS, bot_id_for
from app.agents.academy.perception import leaks_future, time_box
from app.agents.academy.runtime import checkpointer, ensure_checkpointer, memory_store, thread_id

_LINE = ChatPromptTemplate.from_messages([
    ("system", "{persona}\n{time_box}"),
    ("human", "频道记录：\n{transcript}\n\n现在轮到你说。{instruction}"),
])


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
    speakers: list
    index: int
    turns: list


def bind_time(state: SceneState) -> SceneState:
    """时间节点只确认本集坐标，不生成台词。"""
    return {
        "episode_id": (state.get("episode_id") or "").upper(),
        "turns": list(state.get("turns") or []),
        "index": 0,
    }


def plan_cast(state: SceneState) -> SceneState:
    from app.agents.academy.harness import opening_order
    from app.services.academy.bots import wake_bot

    if state.get("mode") == "reply":
        mention = state.get("mention")
        quote_who = (state.get("quote") or {}).get("who")
        speakers = []
        if mention in CHARACTERS:
            speakers.append(mention)
        if quote_who in CHARACTERS and quote_who not in speakers:
            speakers.append(quote_who)
        if not speakers:
            last = state.get("last_who")
            pool = [bot_id_for(key) for key in CHARACTERS if key != last]
            picked = wake_bot(pool, bot_id_for(last) if last else None)
            speakers = [picked.removeprefix("bot_")]
            turns = int(state.get("user_turns") or 0)
            if turns and turns % 3 == 0 and speakers[-1] != "shanyu":
                speakers.append("shanyu")
        else:
            speakers = speakers[:2]
    else:
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
    channel: list
    private: list
    memories: list
    line: dict


def recall(state: BotState, config, *, store) -> BotState:
    bot_id = bot_id_for(state.get("character_key") or "")
    items = store.search((bot_id, "canon"), limit=6)
    texts = [str(item.value.get("text") or "") for item in items if item.value.get("text")]
    return {"memories": texts}


async def utter(state: BotState) -> BotState:
    from app.agents.academy.harness import _fallback, speak
    from app.services.academy.bots import identity_box

    key = state.get("character_key") or ""
    episode_id = state.get("episode_id") or ""
    title = state.get("episode_title") or episode_id
    memories = "；".join(state.get("memories") or []) or "还没有新的自我感知"
    own = " / ".join(str(row.get("text") or "") for row in (state.get("private") or [])[-4:]) or "还没开口"
    box = (
        f"{time_box(key, episode_id, title)}\n{identity_box(key)}\n"
        f"你记得的更新：{memories}\n你自己说过：{own}"
    )
    line = await speak(
        key,
        episode_title=title,
        task=state.get("task") or "",
        child_talent=state.get("child_talent") or "",
        prior=list(state.get("channel") or []),
        instruction=state.get("instruction") or "",
        time_box=box,
        prompt=_LINE,
    )
    if leaks_future(line["text"], episode_id):
        line = {"who": key, "text": _fallback(CHARACTERS[key])}
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


def build_bot_graph(character_key: str):
    graph = StateGraph(BotState)
    graph.add_node("recall", recall)
    graph.add_node("utter", utter)
    graph.add_node("note", note)
    graph.set_entry_point("recall")
    graph.add_edge("recall", "utter")
    graph.add_edge("utter", "note")
    graph.add_edge("note", END)
    return graph.compile(checkpointer=checkpointer(), store=memory_store())


def bot_graph(character_key: str):
    if character_key not in _BOTS:
        _BOTS[character_key] = build_bot_graph(character_key)
    return _BOTS[character_key]


def _hint(state: SceneState, key: str) -> str:
    spoken = "像平时聊天，别像念稿。可以带一个表情，别连着堆。"
    if key == "shanyu" and state.get("mode") != "reply":
        return f"导师收尾。点明今晚训练：{state.get('task') or '去打卡'}。口语，一句。"
    quote = state.get("quote") or {}
    if state.get("mode") == "reply" and state.get("mention") == key:
        return f"孩子点名要你回。直接接话，别绕。{spoken}一句。"
    if state.get("mode") == "reply" and quote.get("who") == key:
        snippet = str(quote.get("text") or "")[:40]
        return f"孩子引用了你这句「{snippet}」。顺着这句往下说，别原样复读。{spoken}"
    if state.get("mode") == "reply":
        return f"直接接孩子最后一句。{spoken}不要复读别人的例句。一句。"
    return "接上一句，说出你在这一集画里的真实想法。口语，不要复读，不要剧透后面。"


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
    from app.agents.academy.harness import _fallback

    await ensure_checkpointer()
    speakers = list(state.get("speakers") or [])
    index = int(state.get("index") or 0)
    if index >= len(speakers):
        return {}
    key = speakers[index]
    episode_id = state.get("episode_id") or ""
    result = await bot_graph(key).ainvoke(
        {
            "character_key": key,
            "episode_id": episode_id,
            "episode_title": state.get("episode_title") or episode_id,
            "task": state.get("task") or "",
            "child_talent": state.get("child_talent") or "",
            "child_user_id": int(state.get("child_user_id") or 0),
            "instruction": _hint(state, key),
            "channel": _channel(state),
        },
        {"configurable": {"thread_id": thread_id(state.get("child_user_id"), episode_id, key)}},
    )
    line = result.get("line") or {"who": key, "text": _fallback(CHARACTERS[key]), "bot_id": bot_id_for(key)}
    quote = state.get("quote") or {}
    if quote.get("text") and (key == state.get("mention") or key == quote.get("who")):
        line = {**line, "quote": {"who": quote.get("who"), "text": quote.get("text")}}
    turns = list(state.get("turns") or []) + [line]
    return {"turns": turns, "index": index + 1}


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
