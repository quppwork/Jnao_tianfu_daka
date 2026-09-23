"""学院 harness — Scene Manager 调度 + 角色卡出话。无样例台词兜底。"""

from __future__ import annotations

import random
import re
from difflib import SequenceMatcher

from app.agents.academy.characters import CHARACTERS, get_character, system_prompt
from app.services.doubao_client import chat_completion

UNLOCK_PERCENT = 90

_INTENTS = (
    ("train", re.compile(r"训练|打卡|站桩|练|作业|考试|闯关|学习")),
    ("feel", re.compile(r"累|不想|放弃|难|烦|怕|紧张|摆烂|躺平")),
    ("ep", re.compile(r"剧情|这一集|师父|秘籍|短剧|视频|故事")),
    ("greet", re.compile(r"^(你好|在吗|大家好|哈喽|嗨)")),
)

_SAY = re.compile(r"(?im)^\s*Say\s*[:：]\s*(.+?)\s*$")
_THOUGHT = re.compile(r"(?im)^\s*Thought\s*[:：]\s*(.+?)\s*(?=^\s*(?:Action|Observation|Say)\s*[:：]|\Z)")
_ACTION = re.compile(r"(?im)^\s*Action\s*[:：]\s*(\w+)")
_OBS = re.compile(r"(?im)^\s*Observation\s*[:：]\s*(.+?)\s*(?=^\s*(?:Thought|Action|Say)\s*[:：]|\Z)")
_REACT_BLOCK = re.compile(
    r"(?is)Thought\s*[:：].*?Action\s*[:：].*?Observation\s*[:：].*?Say\s*[:：]\s*(.+?)(?:\n|$)"
)
_ACTIONS = frozenset({"answer", "example", "react", "redirect", "retrieve"})


def parse_react_say(raw: str | None) -> str:
    """从 ReAct 文本里抽出 Say 那一句；没有标记时退回最后一行口语。"""
    text = (raw or "").strip()
    if not text:
        return ""
    matched = _SAY.findall(text)
    if matched:
        return matched[-1].strip().strip("「」\"'“”")
    block = _REACT_BLOCK.search(text)
    if block:
        return block.group(1).strip().strip("「」\"'“”")
    # 模型有时只回一句口语
    if "Thought" not in text and "Action" not in text:
        return text.splitlines()[0].strip().strip("「」\"'“”")
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line or re.match(r"^(Thought|Action|Observation)\s*[:：]", line, re.I):
            continue
        return line.strip("「」\"'“”")
    return ""


def parse_react_scratch(raw: str | None) -> dict[str, str]:
    """解析 Thought / Action / Observation（LangGraph reason 节点用）。"""
    text = (raw or "").strip()
    thought = ""
    action = "answer"
    observation = ""
    if text:
        m = _THOUGHT.search(text)
        if m:
            thought = m.group(1).strip()
        m = _ACTION.search(text)
        if m:
            token = m.group(1).strip().lower()
            action = token if token in _ACTIONS else "answer"
        m = _OBS.search(text)
        if m:
            observation = m.group(1).strip()
        if not thought and "Thought" not in text:
            thought = text.splitlines()[0].strip()[:120]
    return {"thought": thought, "action": action, "observation": observation}


def format_scratch(scratch: dict | None) -> str:
    row = scratch or {}
    return (
        f"Thought: {row.get('thought') or '（无）'}\n"
        f"Action: {row.get('action') or 'answer'}\n"
        f"Observation: {row.get('observation') or '（无）'}"
    )


def apply_observe(
    scratch: dict | None,
    *,
    drama_notes: str = "",
    channel: list[dict] | None = None,
    user_ask: str = "",
    episode_id: str | None = None,
    character_key: str = "",
) -> dict[str, str]:
    """Observation = 全局图认知 + 检索笔记；不再塞事实种子/人设兜底句。"""
    del user_ask, episode_id, character_key
    out = dict(scratch or {})
    bits: list[str] = []
    if out.get("observation"):
        bits.append(str(out["observation"]))
    notes = (drama_notes or "").strip()
    if notes:
        bits.append(notes)
    last_peer = ""
    for row in reversed(channel or []):
        who = row.get("who")
        if who and who not in ("me", "user"):
            last_peer = f"{who}说：{row.get('text') or ''}"
            break
    if last_peer:
        bits.append(last_peer)
    out["observation"] = "；".join(bits)[:400] if bits else ""
    out["action"] = out.get("action") or "answer"
    return out



def should_unlock(percent: float) -> bool:
    return float(percent) >= UNLOCK_PERCENT


def detect_intent(text: str) -> str:
    raw = (text or "").strip()
    for key, pattern in _INTENTS:
        if pattern.search(raw):
            return key
    return "off"


def opening_order(talent: str | None, episode_id: str | None = None) -> list[str]:
    from app.agents.academy.scene import select_speakers

    return select_speakers(
        episode_id=episode_id,
        mode="opening",
        child_talent=talent,
    )


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


def wake_speakers(
    *,
    mention: str | None,
    quote_who: str | None,
    last_who: str | None,
    n: int = 2,
    episode_id: str | None = None,
) -> list[str]:
    from app.agents.academy.scene import select_speakers

    return select_speakers(
        episode_id=episode_id,
        mode="reply",
        mention=mention,
        quote_who=quote_who,
        last_who=last_who,
        n=n,
    )


def _norm(text: str | None) -> str:
    return re.sub(r"[\s\W_]+", "", (text or "").strip().lower(), flags=re.U)


def alike(a: str | None, b: str | None, *, threshold: float = 0.72) -> bool:
    """原样或高度相似算复读。短句互含不再一刀切，避免「种姓要点」答句被旧台词误杀。"""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    # 仅当较短句足够长，且几乎占满较长句时，才视为互含复读
    if len(shorter) >= 10 and shorter in longer and len(shorter) / max(len(longer), 1) >= 0.82:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= threshold


def prior_said(prior: list[dict] | None) -> list[str]:
    """只收集角色已说的话，避免把孩子原话当「复读」禁掉回礼。"""
    out: list[str] = []
    for row in prior or []:
        who = row.get("who")
        if who in ("me", "user"):
            continue
        text = str(row.get("text") or "").strip()
        if text:
            out.append(text)
    return out


def last_user_ask(prior: list[dict] | None) -> str:
    for row in reversed(prior or []):
        if row.get("who") in ("me", "user"):
            return str(row.get("text") or "").strip()
    return ""


_ROBOT = re.compile(
    r"人工智能|作为\s*AI|我是语言模型|根据(?:资料|上文)|综上所述|值得注意的是|"
    r"作为一名|简单来说吧|总而言之",
    re.I,
)
_LEAD_OK = frozenset({"answer", "example", "retrieve"})


def looks_robotic(text: str | None) -> bool:
    raw = (text or "").strip()
    if not raw:
        return True
    if _ROBOT.search(raw):
        return True
    # 「我问…老师说…」讲解腔
    if "老师说" in raw and ("问：" in raw or "问:" in raw or "我问" in raw or "问：" in raw.replace("：", ":")):
        return True
    if "老师说" in raw and "问" in raw[:16]:
        return True
    return False


def looks_echo(text: str | None, user_ask: str | None) -> bool:
    """几乎只是复述孩子问句，或整段只抛无关新问题。寒暄回礼不算复读。"""
    raw = (text or "").strip()
    ask = (user_ask or "").strip()
    if not raw:
        return True
    if is_greeting(ask):
        return False
    if ask and alike(raw, ask, threshold=0.78):
        return True
    ask_core = re.sub(r"[？?！!。.~～\s]+", "", ask)
    body = re.sub(r"[？?！!。.~～\s]+", "", raw)
    if ask_core and len(ask_core) >= 4 and ask_core in body and len(body) < len(ask_core) + 14:
        return True
    qmarks = raw.count("？") + raw.count("?")
    if ask_core and body and qmarks >= 1:
        # 用户问句前几字几乎没出现，却在抛新问题
        if ask_core[:4] not in body and body[:4] not in ask_core:
            if raw.rstrip().endswith(("？", "?")) or qmarks >= 2:
                return True
    return False


def misses_ask(text: str | None, user_ask: str | None) -> bool:
    """沾了题面词却没答到因果/是否——典型样例跑偏。寒暄不套此规则。"""
    raw = (text or "").strip()
    ask = (user_ask or "").strip()
    if not raw or not ask:
        return False
    if is_greeting(ask):
        return False
    if "为什么" in ask or "为啥" in ask or "咋" in ask:
        if not any(token in raw for token in ("因为", "所以", "才", "科举", "血统", "锁", "打开", "撕", "撬", "怕")):
            return True
    if any(token in ask for token in ("吗", "有没有", "当上", "称帝", "皇帝")):
        if not any(token in raw for token in ("当", "称", "有", "没有", "是", "不是", "四年", "大齐", "撑")):
            return True
    return False


def clamp_scratch(scratch: dict | None, instruction: str) -> dict[str, str]:
    """主答禁止 redirect，避免赢者式跳题。"""
    out = dict(scratch or {})
    action = (out.get("action") or "answer").lower()
    if "主答" in (instruction or "") and action not in _LEAD_OK:
        out["action"] = "answer"
        thought = (out.get("thought") or "").strip()
        out["thought"] = (thought + "；主答必须先答孩子").strip("；")
    return out


def _clean_line(
    text: str | None,
    *,
    avoid: list[str] | None = None,
    user_ask: str = "",
) -> str:
    """只挡空句、人机腔、纯复述问句、明显答偏。不再因与频道旧句相似而丢弃。"""
    del avoid
    raw = (text or "").strip().splitlines()[0].strip() if text else ""
    raw = raw.strip("「」\"'“”")
    if not raw or looks_robotic(raw) or looks_echo(raw, user_ask) or misses_ask(raw, user_ask):
        return ""
    return raw[:80]


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


def _persona_system(
    key: str,
    *,
    episode_title: str,
    task: str,
    child_talent: str,
    episode_id: str | None,
    time_box: str,
) -> str:
    del time_box
    return system_prompt(
        CHARACTERS[key],
        episode_title=episode_title,
        task=task,
        child_talent=child_talent,
        episode_id=episode_id,
    )


def _reason_user_message(transcript: str, instruction: str, avoid: list[str]) -> str:
    del transcript, instruction, avoid
    return ""


def _say_user_message(
    transcript: str,
    instruction: str,
    avoid: list[str],
    scratch: dict | None,
    *,
    drama_notes: str = "",
    user_ask: str = "",
    scene_context: str = "",
) -> str:
    del scratch, avoid
    notes = (drama_notes or "").strip() or "（本轮无已知事件）"
    ask = (user_ask or "").strip() or "（接上一句）"
    scene = (scene_context or "").strip() or "（无）"
    hint = (instruction or "").strip()
    policy = f"本轮要求：{hint}\n\n" if hint else ""
    if is_greeting(ask):
        return (
            f"{policy}"
            f"频道记录：\n{transcript}\n\n"
            f"孩子说：{ask}\n\n"
            "这是打招呼。用角色卡口吻回一句问候即可，不要提剧情、训练或历史课。"
            "不要引号，不要旁白。"
        )
    return (
        f"{policy}"
        f"场景：{scene}\n\n"
        f"频道记录：\n{transcript}\n\n"
        f"你截至本集已知：\n{notes}\n\n"
        f"孩子说：{ask}\n\n"
        "只用你已知的事，用角色卡口吻回一句口语（60字内）。"
        "不知道的事不要编。不要引号，不要旁白。"
    )


async def reason(
    key: str,
    *,
    episode_title: str,
    task: str,
    child_talent: str,
    prior: list[dict],
    instruction: str,
    time_box: str = "",
    episode_id: str | None = None,
) -> dict[str, str]:
    """空 scratch 占位；认知注入在 observe / drama_notes。"""
    del key, episode_title, task, child_talent, prior, instruction, time_box, episode_id
    return {"thought": "", "action": "answer", "observation": ""}


async def say_line(
    key: str,
    *,
    episode_title: str,
    task: str,
    child_talent: str,
    prior: list[dict],
    instruction: str,
    scratch: dict | None,
    time_box: str = "",
    episode_id: str | None = None,
    drama_notes: str = "",
) -> dict | None:
    """角色卡 system + 认知/场景 user；模型失败或不合格 → None（无台词兜底）。"""
    if key not in CHARACTERS:
        return None
    avoid = prior_said(prior)
    ask = last_user_ask(prior)
    notes = (drama_notes or "").strip()
    if not notes and scratch and scratch.get("observation"):
        notes = str(scratch.get("observation") or "").strip()
    from app.agents.academy.packs import get_pack

    pack = get_pack(episode_id)
    scene = pack.scene_context if pack else ""
    system = _persona_system(
        key,
        episode_title=episode_title,
        task=task,
        child_talent=child_talent,
        episode_id=episode_id,
        time_box=time_box,
    )
    user_message = _say_user_message(
        _transcript(prior),
        instruction,
        avoid,
        scratch,
        drama_notes=notes,
        user_ask=ask,
        scene_context=scene,
    )
    text = await chat_completion(
        system_prompt=system,
        user_message=user_message,
        max_tokens=120,
        timeout=25,
        feature="academy",
        disable_thinking=True,
    )
    if text is None:
        return None
    say = parse_react_say(text)
    if not say and text:
        say = text.strip().splitlines()[0].strip()
    cleaned = _clean_line(say, avoid=avoid, user_ask=ask)
    if not cleaned:
        return None
    return {"who": key, "text": cleaned}


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
    drama_notes: str = "",
) -> dict | None:
    """兼容入口：reason → observe → say。失败返回 None。"""
    del prompt
    scratch = await reason(
        key,
        episode_title=episode_title,
        task=task,
        child_talent=child_talent,
        prior=prior,
        instruction=instruction,
        time_box=time_box,
        episode_id=episode_id,
    )
    scratch = apply_observe(
        scratch,
        drama_notes=drama_notes,
        channel=prior,
        user_ask=last_user_ask(prior),
        episode_id=episode_id,
        character_key=key,
    )
    return await say_line(
        key,
        episode_title=episode_title,
        task=task,
        child_talent=child_talent,
        prior=prior,
        instruction=instruction,
        scratch=scratch,
        time_box=time_box,
        episode_id=episode_id,
        drama_notes=drama_notes,
    )


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
