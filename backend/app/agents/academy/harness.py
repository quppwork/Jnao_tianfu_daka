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


def _fallback(char: Character) -> str:
    return random.choice(char.samples)


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
    prompt=None,
) -> dict:
    char = CHARACTERS[key]
    fallback = _fallback(char)
    transcript = _transcript(prior)
    if prompt is not None:
        messages = prompt.format_messages(
            persona=system_prompt(
                char,
                episode_title=episode_title,
                task=task,
                child_talent=child_talent,
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
) -> list[dict]:
    from app.agents.academy.graph import run_scene

    return await run_scene({
        "mode": "opening",
        "episode_id": episode_id,
        "episode_title": episode_title,
        "task": task,
        "child_talent": child_talent,
        "child_user_id": int(child_user_id or 0),
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
        "turns": [],
    })
