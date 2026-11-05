"""Guide 受控写（R5）— 白名单 + 确认卡载荷 + 落库 + 审计。

当前白名单仅「习惯/意向画像」类；后续扩 WRITE_SPECS 即可。
确认前不落库：propose_* 只返回 confirm action；execute 经 API 校验白名单后才写。
禁止：排课、Tier、打卡提交等（不在白名单即拒绝）。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.agents.guide.student_memory import (
    _SKILL_NAMES,
    load_guide_memory,
    save_guide_memory,
)
from app.core.logger import get_logger
from app.db.models import ChildUser

logger = get_logger("guide.writes")

AUDIT_KEY = "guide_write_audit"
AUDIT_MAX = 30

# 显式「请记下」意图，避免每句提到分钟都弹确认
_SAVE_INTENT = ("记住", "记下", "帮我记", "记下来", "帮我保存", "保存一下", "记一下")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _exec_preferred_minutes(db: Session, child_user_id: int, args: dict) -> dict[str, Any]:
    mins = int(args.get("minutes") or 0)
    if not (5 <= mins <= 300):
        return {"ok": False, "error": "时长需在 5～300 分钟"}
    mem = load_guide_memory(db, child_user_id)
    prefs = dict(mem.get("preferences") or {})
    prefs["preferred_minutes"] = mins
    prefs["preferred_minutes_source"] = "confirmed"
    mem["preferences"] = prefs
    save_guide_memory(db, child_user_id, mem)
    return {"ok": True, "preferred_minutes": mins}


def _exec_remind_skill(db: Session, child_user_id: int, args: dict) -> dict[str, Any]:
    skill = str(args.get("skill") or "").strip()
    if skill not in _SKILL_NAMES:
        return {"ok": False, "error": "不支持的技能名"}
    mem = load_guide_memory(db, child_user_id)
    prefs = dict(mem.get("preferences") or {})
    skills = [str(s) for s in (prefs.get("remind_skills") or []) if s]
    if skill not in skills:
        skills.append(skill)
    prefs["remind_skills"] = skills[-5:]
    mem["preferences"] = prefs
    # 同步进 recent_focus，便于策略/记忆引用
    focus = list(mem.get("recent_focus") or [])
    if skill not in focus:
        focus.append(skill)
    mem["recent_focus"] = focus[-8:]
    save_guide_memory(db, child_user_id, mem)
    return {"ok": True, "remind_skills": prefs["remind_skills"]}


# name -> (说明, 执行器) — 扩白名单只加这里
WRITE_SPECS: dict[str, tuple[str, Callable[..., dict[str, Any]]]] = {
    "save_preferred_minutes": (
        "记下意向训练时长（分钟），写入 guide_memory.preferences",
        _exec_preferred_minutes,
    ),
    "save_remind_skill": (
        "记下下次多留意的技能，写入 guide_memory.preferences.remind_skills",
        _exec_remind_skill,
    ),
}

WRITE_WHITELIST = frozenset(WRITE_SPECS)


def list_write_ops() -> list[dict[str, str]]:
    return [{"name": n, "desc": d} for n, (d, _) in WRITE_SPECS.items()]


def confirm_action(
    write_op: str,
    args: dict[str, Any],
    *,
    label: str,
    preview: str,
) -> dict[str, Any] | None:
    if write_op not in WRITE_WHITELIST:
        return None
    clean_args = {
        str(k): v
        for k, v in (args or {}).items()
        if k and v is not None and str(v).strip() != ""
    }
    return {
        "type": "confirm",
        "write_op": write_op,
        "args": clean_args,
        "label": label,
        "preview": preview,
        "cancel_label": "暂不",
    }


def propose_write_confirms(message: str) -> list[dict[str, Any]]:
    """从用户话提出确认卡（不落库）。无显式「记下」意图则不提。"""
    text = (message or "").strip()
    if not text or not any(k in text for k in _SAVE_INTENT):
        return []

    out: list[dict[str, Any]] = []
    m = re.search(r"(?:想练|练|训练)?\s*(\d{1,3})\s*分钟", text)
    if not m:
        m = re.search(r"(\d{1,3})\s*分钟", text)
    if m:
        mins = int(m.group(1))
        if 5 <= mins <= 300:
            act = confirm_action(
                "save_preferred_minutes",
                {"minutes": mins},
                label=f"确认记下：想练 {mins} 分钟",
                preview="确认后写入训练偏好，老师下次开场/对话会参考；不会改今日排课。",
            )
            if act:
                out.append(act)

    for sk in _SKILL_NAMES:
        if sk in text and any(
            k in text for k in ("弱项", "留意", "关注", "提醒", "多练")
        ):
            act = confirm_action(
                "save_remind_skill",
                {"skill": sk},
                label=f"确认记下：下次多留意「{sk}」",
                preview="确认后记入偏好提醒，不会改档位或排课。",
            )
            if act:
                out.append(act)
            break

    return out[:2]


def append_write_audit(
    db: Session,
    child_user_id: int,
    *,
    write_op: str,
    args: dict[str, Any],
    result: dict[str, Any],
) -> None:
    child = db.get(ChildUser, child_user_id)
    if not child:
        return
    pj = dict(child.profile_json or {})
    rows = list(pj.get(AUDIT_KEY) or [])
    rows.append({
        "at": _now_iso(),
        "write_op": write_op,
        "args": dict(args or {}),
        "ok": bool(result.get("ok")),
        "error": result.get("error"),
    })
    pj[AUDIT_KEY] = rows[-AUDIT_MAX:]
    child.profile_json = pj
    try:
        flag_modified(child, "profile_json")
        db.commit()
    except Exception:
        db.rollback()


def execute_write(
    db: Session,
    child_user_id: int,
    write_op: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """白名单校验后执行；确认前不得调用。"""
    name = str(write_op or "").strip()
    if name not in WRITE_WHITELIST:
        logger.warning(f"guide write rejected uid={child_user_id} op={name}")
        return {"ok": False, "error": "不允许的写操作", "write_op": name}

    _desc, fn = WRITE_SPECS[name]
    _ = _desc
    try:
        result = fn(db, child_user_id, dict(args or {}))
    except Exception as e:
        logger.exception(f"guide write failed uid={child_user_id} op={name}")
        result = {"ok": False, "error": str(e)[:120]}

    result = dict(result or {})
    result.setdefault("write_op", name)
    append_write_audit(
        db, child_user_id, write_op=name, args=dict(args or {}), result=result
    )
    logger.info(
        f"guide_write uid={child_user_id} op={name} ok={result.get('ok')} args={args}"
    )
    return result
