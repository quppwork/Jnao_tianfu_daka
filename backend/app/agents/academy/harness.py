"""学院 harness — 一个编排，多个角色智能体。角色之间不互相调用，只看频道记录。"""

from __future__ import annotations

import random
import re
from difflib import SequenceMatcher

from app.agents.academy.characters import CHARACTERS, KIDS, TALENT_CHAR, Character, get_character, system_prompt
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
    """环境观察（主流 ReAct 的 Observation 由环境回填，不单靠模型编）。"""
    from app.agents.academy.packs import pack_fact_seed

    out = dict(scratch or {})
    action = (out.get("action") or "answer").lower()
    bits: list[str] = []
    if out.get("observation"):
        bits.append(str(out["observation"]))
    ask = (user_ask or "").strip() or last_user_ask(channel)
    fact = pack_fact_seed(episode_id, ask, character_key)
    if fact and action in ("answer", "example", "retrieve", "react"):
        bits.append("常识要点：" + fact)
    notes = (drama_notes or "").strip()
    if notes and action in ("answer", "example", "retrieve"):
        bits.append("短剧资料要点：" + " ".join(notes.split())[:220])
    last_peer = ""
    for row in reversed(channel or []):
        who = row.get("who")
        if who and who not in ("me", "user"):
            last_peer = f"{who}说：{row.get('text') or ''}"
            break
    if last_peer and action in ("react", "answer"):
        bits.append(last_peer)
    out["observation"] = "；".join(bits)[:400] if bits else (out.get("observation") or "先按人设口语接孩子。")
    return out



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


def wake_speakers(
    *,
    mention: str | None,
    quote_who: str | None,
    last_who: str | None,
    n: int = 2,
) -> list[str]:
    """会话回复随机唤醒。点名、引用的人先开口，其余从同学里抽，尽量不连着同一个。"""
    pool = [key for key in KIDS if key != last_who] or list(KIDS)
    speakers: list[str] = []
    if mention in CHARACTERS:
        speakers.append(mention)
    if quote_who in CHARACTERS and quote_who not in speakers:
        speakers.append(quote_who)
    rest = [key for key in pool if key not in speakers]
    random.shuffle(rest)
    for key in rest:
        if len(speakers) >= n:
            break
        speakers.append(key)
    if len(speakers) < n:
        for key in KIDS:
            if key not in speakers:
                speakers.append(key)
            if len(speakers) >= n:
                break
    return speakers[:n]


def _norm(text: str | None) -> str:
    return re.sub(r"[\s\W_]+", "", (text or "").strip().lower(), flags=re.U)


def alike(a: str | None, b: str | None, *, threshold: float = 0.72) -> bool:
    """原样、互相包含、或高度相似都算复读。"""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= threshold


def prior_said(prior: list[dict] | None) -> list[str]:
    out: list[str] = []
    for row in prior or []:
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
    """几乎只是复述孩子问句，或整段只抛无关新问题。"""
    raw = (text or "").strip()
    ask = (user_ask or "").strip()
    if not raw:
        return True
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
    """沾了题面词却没答到因果/是否——典型样例跑偏。"""
    raw = (text or "").strip()
    ask = (user_ask or "").strip()
    if not raw or not ask:
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
    fallback: str,
    *,
    avoid: list[str] | None = None,
    user_ask: str = "",
) -> str:
    raw = (text or "").strip().splitlines()[0].strip() if text else ""
    raw = raw.strip("「」\"'“”")
    if not raw or looks_robotic(raw) or looks_echo(raw, user_ask) or misses_ask(raw, user_ask):
        return fallback
    raw = raw[:80]
    for old in avoid or []:
        if alike(raw, old):
            return fallback
    return raw


def _fallback(
    char: Character,
    episode_id: str | None = None,
    *,
    avoid: list[str] | None = None,
    user_ask: str = "",
) -> str:
    from app.agents.academy.packs import pack_fact_seed, pack_synopsis
    from app.agents.academy.perception import sample_lines
    from app.agents.academy.turn import prepare_turn

    seen = list(avoid or [])
    ctx = prepare_turn(
        user_text=user_ask,
        episode_id=episode_id or "",
        character_keys=[char.key],
    )
    skill = ctx.skill
    if skill == "summary":
        synopsis = ctx.synopsis or pack_synopsis(episode_id)
        if synopsis and not any(alike(synopsis, old) for old in seen):
            return synopsis[:80]
        return synopsis[:80] if synopsis else "这一集我还在看。"
    if user_ask and skill == "answer":
        fact = ctx.fact_for(char.key) or pack_fact_seed(episode_id, user_ask, char.key)
        if fact and not any(alike(fact, old) for old in seen):
            return fact
        if fact:
            return "对，就按刚才那句要点。"
        # 事实题禁止抽无关样例（会答非所问）
        return "这句我还没想圆，你再问细一点。"
    if user_ask:
        return "嗯，我听着。"
    pool = list(sample_lines(char.key, episode_id) or char.samples)
    fresh = [line for line in pool if not any(alike(line, old) for old in seen)]
    choices = fresh or pool
    return random.choice(choices) if choices else "嗯。"


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
    system = system_prompt(
        CHARACTERS[key],
        episode_title=episode_title,
        task=task,
        child_talent=child_talent,
        episode_id=episode_id,
    )
    if time_box:
        system = f"{system}\n{time_box}"
    return system


def _reason_user_message(transcript: str, instruction: str, avoid: list[str]) -> str:
    banned = "\n".join(f"- {line}" for line in avoid[-12:]) or "- （还没有）"
    lead = "主答" in (instruction or "")
    action_line = (
        "Action: answer / example / retrieve（主答三选一，禁止 redirect）"
        if lead
        else "Action: answer / example / react / redirect / retrieve（五选一）"
    )
    return (
        f"频道记录：\n{transcript}\n\n"
        f"禁复读：\n{banned}\n\n"
        f"{instruction}\n\n"
        "这是 ReAct 的思考步（不要写 Say，不要对频道说话）：\n"
        "Thought: 孩子在问什么？要点事实是什么（可用常识）？我主答还是补半句？\n"
        f"{action_line}\n"
        "Observation: 你准备用的事实要点（一句话；资料会由环境再补）"
    )


def _say_user_message(
    transcript: str,
    instruction: str,
    avoid: list[str],
    scratch: dict | None,
) -> str:
    banned = "\n".join(f"- {line}" for line in avoid[-12:]) or "- （还没有）"
    return (
        f"频道记录：\n{transcript}\n\n"
        f"禁复读：\n{banned}\n\n"
        f"{instruction}\n\n"
        f"你已完成的 ReAct 草稿：\n{format_scratch(scratch)}\n\n"
        "只输出要对频道说的一句口语（60字内）。\n"
        "先答孩子刚说的那句。历史、人物、剧情用常识说准，再带你的语气。"
        "不要复述问句，不要改答别的题，不要 Thought/Action，不要引号。"
    )


async def polish_seed(
    key: str,
    *,
    seed: str,
    user_ask: str,
    episode_title: str,
    task: str,
    child_talent: str,
    episode_id: str | None,
    time_box: str,
    avoid: list[str],
    instruction: str = "",
) -> str:
    """兜底前再用模型润色：通用知识答准 + 人设口语；失败返回空。"""
    system = _persona_system(
        key,
        episode_title=episode_title,
        task=task,
        child_talent=child_talent,
        episode_id=episode_id,
        time_box=time_box,
    )
    banned = " / ".join(avoid[-6:]) or "（无）"
    ask = user_ask or "（接上一句）"
    text = await chat_completion(
        system_prompt=system,
        user_message=(
            f"孩子刚说：{ask}\n"
            f"{instruction}\n"
            f"口吻种子（只借语气，勿整句照搬）：{seed}\n"
            f"不要接近：{banned}\n\n"
            "用常识把孩子的问题答准，再用你的人设说成一句口语（60字内）。"
            "不要复述问句，不要只抛新问题，不要引号。"
        ),
        max_tokens=120,
        timeout=20,
        feature="academy",
        disable_thinking=True,
    )
    say = parse_react_say(text)
    if not say and text:
        say = text.strip().splitlines()[0].strip()
    say = (say or "").strip().strip("「」\"'“”")[:80]
    if not say or looks_robotic(say) or looks_echo(say, user_ask):
        return ""
    if any(alike(say, old) for old in avoid):
        return ""
    return say


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
    """这个角色的 ReAct 思考：模型写 Thought/Action。限流或空回复时用本地感知顶上。"""
    from app.agents.academy.skills import perceive, skill_instruction

    avoid = prior_said(prior)
    text = await chat_completion(
        system_prompt=_persona_system(
            key,
            episode_title=episode_title,
            task=task,
            child_talent=child_talent,
            episode_id=episode_id,
            time_box=time_box,
        ),
        user_message=_reason_user_message(_transcript(prior), instruction, avoid),
        max_tokens=180,
        timeout=25,
        feature="academy",
        disable_thinking=True,
    )
    if text:
        return clamp_scratch(parse_react_scratch(text), instruction)
    seen = perceive(
        key,
        episode_id=episode_id or "",
        episode_title=episode_title,
        channel=prior,
        index=0,
    )
    skill = seen.get("skill") or "answer"
    action = {
        "summary": "retrieve",
        "redirect_qa": "redirect",
        "comfort": "react",
        "greet": "react",
    }.get(skill, "answer")
    return clamp_scratch(
        {
            "thought": skill_instruction(seen)[:160],
            "action": action,
            "observation": (seen.get("fact") or seen.get("synopsis") or "")[:180],
        },
        instruction,
    )


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
) -> dict:
    """LangGraph say：模型出话；限流/空响应时立刻走事实种子，不再连打烧配额。"""
    char = CHARACTERS[key]
    avoid = prior_said(prior)
    ask = last_user_ask(prior)
    seed = _fallback(char, episode_id, avoid=avoid, user_ask=ask)
    system = _persona_system(
        key,
        episode_title=episode_title,
        task=task,
        child_talent=child_talent,
        episode_id=episode_id,
        time_box=time_box,
    )
    user_message = _say_user_message(_transcript(prior), instruction, avoid, scratch)

    async def _once(msg: str) -> str | None:
        text = await chat_completion(
            system_prompt=system,
            user_message=msg,
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
        return (say or "").strip() or ""

    say = await _once(user_message)
    if say is None:
        # 上游空/429：直接事实种子，避免 retry+polish 再打爆 RPM
        return {"who": key, "text": seed}
    cleaned = _clean_line(say, "", avoid=avoid, user_ask=ask)
    if not cleaned:
        say2 = await _once(
            f"{user_message}\n\n上一句撞车、人机腔或没答到。换角度只回一句口语，先答孩子。"
            f"不要接近：{' / '.join(avoid[-6:]) or '（无）'}"
        )
        if say2 is None:
            return {"who": key, "text": seed}
        cleaned = _clean_line(say2, "", avoid=avoid, user_ask=ask)
    if not cleaned:
        polished = await polish_seed(
            key,
            seed=seed,
            user_ask=ask,
            episode_title=episode_title,
            task=task,
            child_talent=child_talent,
            episode_id=episode_id,
            time_box=time_box,
            avoid=avoid,
            instruction=instruction,
        )
        cleaned = polished or seed
    return {"who": key, "text": cleaned or seed}


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
) -> dict:
    """兼容入口：reason → observe → say（与 bot 子图一致）。"""
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
