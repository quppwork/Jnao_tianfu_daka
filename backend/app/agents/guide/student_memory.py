"""Guide 学生记忆（R2）— 滚动摘要 + 结构化资产，存 profile_json.guide_memory。

与 long_term（DB 打卡统计）并列：本模块来自对话，不读晋级内部计数。
"""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import ChildUser

MEMORY_KEY = "guide_memory"
MEMORY_VERSION = 1
MAX_OPEN_INTENTS = 5
MAX_RECENT_FOCUS = 8
MAX_DIGEST_CHARS = 600
HISTORY_KEEP_DEFAULT = 12

_SKILL_NAMES = (
    "超脑阅读",
    "影像追忆",
    "扫描速记",
    "极速运算",
    "极速学习",
    "多元感知",
)

_FOCUS_KEYWORDS = (
    "弱项",
    "晋级",
    "下一等级",
    "打卡",
    "方案",
    "天赋",
    "测评",
    "进度",
    "时长",
)


def _empty_memory() -> dict[str, Any]:
    return {
        "version": MEMORY_VERSION,
        "updated_at": None,
        "preferences": {},
        "open_intents": [],
        "recent_focus": [],
        "rolling_summary": "",
    }


def load_guide_memory(db: Session, child_user_id: int) -> dict[str, Any]:
    child = db.get(ChildUser, child_user_id)
    if not child or not isinstance(child.profile_json, dict):
        return _empty_memory()
    raw = child.profile_json.get(MEMORY_KEY)
    if not isinstance(raw, dict):
        return _empty_memory()
    mem = _empty_memory()
    mem["preferences"] = dict(raw.get("preferences") or {})
    mem["open_intents"] = list(raw.get("open_intents") or [])[:MAX_OPEN_INTENTS]
    mem["recent_focus"] = list(raw.get("recent_focus") or [])[:MAX_RECENT_FOCUS]
    mem["rolling_summary"] = str(raw.get("rolling_summary") or "")[:MAX_DIGEST_CHARS]
    mem["updated_at"] = raw.get("updated_at")
    mem["version"] = int(raw.get("version") or MEMORY_VERSION)
    return mem


def save_guide_memory(db: Session, child_user_id: int, mem: dict[str, Any]) -> None:
    child = db.get(ChildUser, child_user_id)
    if not child:
        return
    payload = {
        "version": MEMORY_VERSION,
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"),
        "preferences": dict(mem.get("preferences") or {}),
        "open_intents": list(mem.get("open_intents") or [])[:MAX_OPEN_INTENTS],
        "recent_focus": list(mem.get("recent_focus") or [])[:MAX_RECENT_FOCUS],
        "rolling_summary": str(mem.get("rolling_summary") or "")[:MAX_DIGEST_CHARS],
    }
    pj = dict(child.profile_json or {})
    pj[MEMORY_KEY] = payload
    child.profile_json = pj
    try:
        flag_modified(child, "profile_json")
        db.commit()
    except Exception:
        db.rollback()


def clear_guide_memory(db: Session, child_user_id: int) -> None:
    child = db.get(ChildUser, child_user_id)
    if not child or not isinstance(child.profile_json, dict):
        return
    if MEMORY_KEY not in child.profile_json:
        return
    pj = dict(child.profile_json)
    pj.pop(MEMORY_KEY, None)
    child.profile_json = pj
    try:
        flag_modified(child, "profile_json")
        db.commit()
    except Exception:
        db.rollback()


def fold_overflow_history(
    messages: list[dict],
    mem: dict[str, Any],
    *,
    keep: int = HISTORY_KEEP_DEFAULT,
) -> tuple[list[dict], dict[str, Any]]:
    """超出 keep 的旧轮次压进 rolling_summary，返回尾部历史 + 更新后的 mem。"""
    msgs = list(messages or [])
    out_mem = deepcopy(mem) if mem else _empty_memory()
    if keep <= 0 or len(msgs) <= keep:
        return msgs, out_mem
    older = msgs[:-keep]
    recent = msgs[-keep:]
    lines: list[str] = []
    for m in older:
        role = "学员" if m.get("role") == "user" else "老师"
        c = str(m.get("content") or "").strip().replace("\n", " ")
        if c:
            lines.append(f"{role}:{c[:80]}")
    chunk = "；".join(lines)
    prev = str(out_mem.get("rolling_summary") or "").strip()
    merged = f"{prev}；{chunk}".strip("；") if prev else chunk
    if len(merged) > MAX_DIGEST_CHARS:
        merged = "…" + merged[-(MAX_DIGEST_CHARS - 1) :]
    out_mem["rolling_summary"] = merged
    return recent, out_mem


def extract_from_user_message(message: str, mem: dict[str, Any]) -> dict[str, Any]:
    """规则抽取偏好 / 未完成意图 / 关注点（不调 LLM，可测）。"""
    text = (message or "").strip()
    out = deepcopy(mem) if mem else _empty_memory()
    if not text:
        return out

    prefs = dict(out.get("preferences") or {})
    m = re.search(r"(?:想练|练|训练)\s*(\d{1,3})\s*分钟", text)
    if not m:
        m = re.search(r"(\d{1,3})\s*分钟", text)
    if m:
        mins = int(m.group(1))
        if 5 <= mins <= 300:
            prefs["preferred_minutes"] = mins
    out["preferences"] = prefs

    focus = list(out.get("recent_focus") or [])
    for sk in _SKILL_NAMES:
        if sk in text and sk not in focus:
            focus.append(sk)
    for kw in _FOCUS_KEYWORDS:
        if kw in text and kw not in focus:
            focus.append(kw)
    out["recent_focus"] = focus[-MAX_RECENT_FOCUS:]

    intents = list(out.get("open_intents") or [])
    is_q = ("？" in text or "?" in text) or any(
        k in text for k in ("怎么", "如何", "什么时候", "为什么", "哪")
    )
    if is_q and any(
        k in text
        for k in ("等级", "晋级", "方案", "弱项", "打卡", "进度", "天赋", "练")
    ):
        brief = text[:60]
        intents = [i for i in intents if i.get("text") != brief]
        intents.append({
            "text": brief,
            "at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"),
        })
        out["open_intents"] = intents[-MAX_OPEN_INTENTS:]

    return out


def to_prompt_block(mem: dict[str, Any] | None) -> str:
    """注入 system；空则返回空串。禁止写入晋级内部计数。"""
    if not mem:
        return ""
    lines: list[str] = []
    digest = str(mem.get("rolling_summary") or "").strip()
    if digest:
        lines.append(f"近期对话摘要: {digest}")
    prefs = mem.get("preferences") or {}
    if isinstance(prefs, dict) and prefs.get("preferred_minutes"):
        src = prefs.get("preferred_minutes_source") or "inferred"
        tag = "已确认" if src == "confirmed" else "提到的"
        lines.append(f"学员{tag}意向时长: {prefs['preferred_minutes']} 分钟")
    if isinstance(prefs, dict):
        remind = [str(s) for s in (prefs.get("remind_skills") or []) if s]
        if remind:
            lines.append(f"学员希望多留意的技能: {', '.join(remind[:5])}")
    focus = [str(x) for x in (mem.get("recent_focus") or []) if x]
    if focus:
        lines.append(f"近期关注: {', '.join(focus[:8])}")
    intents = mem.get("open_intents") or []
    if intents:
        texts = [str(i.get("text") or "").strip() for i in intents if isinstance(i, dict)]
        texts = [t for t in texts if t][-3:]
        if texts:
            lines.append("未完成追问: " + " | ".join(texts))
    if not lines:
        return ""
    return (
        "对话记忆（来自历史聊天摘要与偏好，勿编造、勿展开晋级规则）:\n"
        + "\n".join(lines)
    )
