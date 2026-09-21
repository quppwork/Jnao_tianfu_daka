"""学院 harness — 一个编排，多个角色智能体。角色之间不互相调用，只看频道记录。"""

from __future__ import annotations

import random
import re

from app.agents.academy.characters import CHARACTERS, KIDS, TALENT_CHAR, Character, get_character, system_prompt
from app.services.doubao_client import chat_completion

UNLOCK_PERCENT = 90

_INTENTS = (
    ("train", re.compile(r"训练|打卡|站桩|练|作业|考试|闯关|学习")),
    ("feel", re.compile(r"累|不想|放弃|难|烦|怕|紧张|摆烂|躺平")),
    ("ep", re.compile(r"剧情|这一集|师父|秘籍|短剧|视频|故事")),
    ("greet", re.compile(r"^(你好|在吗|大家好|哈喽|嗨)")),
)


def should_unlock(percent: float) -> bool:
    return float(percent) >= UNLOCK_PERCENT


def detect_intent(text: str) -> str:
    raw = (text or "").strip()
    for key, pattern in _INTENTS:
        if pattern.search(raw):
            return key
    return "off"


def opening_order(talent: str | None) -> list[str]:
    kids = list(KIDS)
    random.shuffle(kids)
    picked = kids[:3]
    lead = TALENT_CHAR.get((talent or "").strip())
    if lead:
        if lead in picked:
            picked.remove(lead)
        else:
            picked = picked[:2]
        picked.insert(0, lead)
    return picked + ["shanyu"]


_QA = re.compile(r"答题|这道题|作业题|解题|怎么算|数学|语文|英语|物理|化学|生物|公式")
_LOW = re.compile(r"累|烦|不想|放弃|难过|害怕|焦虑|崩溃|无聊|讨厌|站不住")
_HIGH = re.compile(r"哈哈|开心|太好了|兴奋|想赢|爽|来比")


def route_topic(text: str) -> str:
    """答题去学科答疑，其余走剧情。"""
    if _QA.search(text or ""):
        return "qa"
    return "plot"


_GREET = re.compile(
    r"^(你好|哈喽|嗨|hi|hello|在吗|早|晚安|吃了吗)[啊呀吧呢哦哈！!。.~～\s]*$",
    re.I,
)


def is_greeting(text: str) -> bool:
    return bool(_GREET.match((text or "").strip()))


def read_mood(text: str) -> str:
    """从这一句看情绪，用来调语气，不改人设。"""
    raw = text or ""
    if _LOW.search(raw):
        return "low"
    if _HIGH.search(raw):
        return "high"
    return "even"


def pick_reply_cast(text: str, talent: str | None, last_who: str | None, user_turns: int) -> list[str]:
    intent = detect_intent(text)
    pools = {
        "train": ["limo", "jiahui", "chenxue", "dani"],
        "feel": ["dani", "shanyu", "jiahui"],
        "ep": ["yuchen", "chenxue", "jiahui", "dani"],
        "greet": ["dani", "yuchen", "chenxue"],
        "off": ["yuchen", "dani", "chenxue", "jiahui", "limo"],
    }
    speakers: list[str] = []
    lead = TALENT_CHAR.get((talent or "").strip())
    if lead and lead != last_who:
        speakers.append(lead)
    for key in pools.get(intent, ["dani"]):
        if key not in speakers and key != last_who:
            speakers.append(key)
            break
    if not speakers:
        speakers.append("dani" if last_who != "dani" else "limo")
    if user_turns and user_turns % 3 == 0:
        speakers = [key for key in speakers if key != "shanyu"][:1]
        speakers.append("shanyu")
    return speakers[:2]


def _clean_line(text: str | None, fallback: str) -> str:
    raw = (text or "").strip().splitlines()[0].strip() if text else ""
    raw = raw.strip("「」\"'“”")
    if not raw or "人工智能" in raw or "作为AI" in raw or "作为 AI" in raw:
        return fallback
    return raw[:80]


def _fallback(char: Character, episode_id: str | None = None) -> str:
    from app.agents.academy.perception import sample_lines

    pool = sample_lines(char.key, episode_id) or char.samples
    return random.choice(pool) if pool else "嗯。"


def _transcript(lines: list[dict]) -> str:
    parts = []
    for row in lines[-8:]:
        who = row.get("who") or ""
        if who == "me":
            extra = ""
            mark = row.get("mention")
            if mark:
                named = get_character(str(mark))
                extra += f"，点名{named.name if named else mark}"
            quoted = row.get("quote") if isinstance(row.get("quote"), dict) else None
            if quoted and quoted.get("text"):
                qwho = quoted.get("who")
                qname = "自己" if qwho == "me" else (get_character(str(qwho)).name if get_character(str(qwho)) else qwho)
                extra += f"，引用{qname}：{quoted.get('text')}"
            parts.append(f"孩子{extra}：{row.get('text') or ''}")
            continue
        char = get_character(who)
        name = char.name if char else who
        parts.append(f"{name}：{row.get('text') or ''}")
    return "\n".join(parts) or "（频道刚打开）"


async def speak(
    key: str,
    *,
    episode_title: str,
    task: str,
    child_talent: str,
    prior: list[dict],
    instruction: str,
    time_box: str = "",
    episode_id: str | None = None,
    prompt=None,
) -> dict:
    char = CHARACTERS[key]
    fallback = _fallback(char, episode_id)
    transcript = _transcript(prior)
    if prompt is not None:
        messages = prompt.format_messages(
            persona=system_prompt(
                char,
                episode_title=episode_title,
                task=task,
                child_talent=child_talent,
                episode_id=episode_id,
            ),
            time_box=time_box,
            transcript=transcript,
            instruction=instruction,
        )
        system = messages[0].content
        user_message = messages[1].content
    else:
        system = system_prompt(
            char,
            episode_title=episode_title,
            task=task,
            child_talent=child_talent,
            episode_id=episode_id,
        )
        if time_box:
            system = f"{system}\n{time_box}"
        user_message = f"频道记录：\n{transcript}\n\n现在轮到你说。{instruction}"
    text = await chat_completion(
        system_prompt=system,
        user_message=user_message,
        max_tokens=180,
        timeout=25,
        feature="academy",
        disable_thinking=True,
    )
    return {"who": key, "text": _clean_line(text, fallback)}


async def opening_turns(
    *,
    episode_id: str,
    episode_title: str,
    task: str,
    child_talent: str,
    child_user_id: int | None = None,
    training_done: bool = True,
) -> list[dict]:
    from app.agents.academy.graph import run_scene

    return await run_scene({
        "mode": "opening",
        "episode_id": episode_id,
        "episode_title": episode_title,
        "task": task,
        "child_talent": child_talent,
        "child_user_id": int(child_user_id or 0),
        "training_done": training_done,
        "prior": [],
        "turns": [],
    })


async def reply_turns(
    user_text: str,
    *,
    episode_id: str,
    episode_title: str,
    task: str,
    child_talent: str,
    prior: list[dict],
    last_who: str | None,
    user_turns: int,
    child_user_id: int | None = None,
    mention: str | None = None,
    quote: dict | None = None,
    topic: str = "plot",
    affect: dict | None = None,
    training_done: bool = True,
    nudge_train: bool = False,
) -> list[dict]:
    from app.agents.academy.graph import run_scene

    return await run_scene({
        "mode": "reply",
        "episode_id": episode_id,
        "episode_title": episode_title,
        "task": task,
        "child_talent": child_talent,
        "child_user_id": int(child_user_id or 0),
        "user_text": user_text,
        "prior": prior,
        "last_who": last_who,
        "user_turns": user_turns,
        "mention": mention,
        "quote": quote,
        "topic": topic,
        "affect": affect or {},
        "training_done": training_done,
        "nudge_train": nudge_train,
        "turns": [],
    })
