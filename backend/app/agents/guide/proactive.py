"""Guide 主动节奏（R8）— 进页一句：掉队召回 / 连打鼓励 / 周简报。

频控：每个训练日最多一条；周简报按 ISO 周；连打按里程碑。
可关：GUIDE_PROACTIVE_ENABLED=0，或 profile_json.guide_proactive.enabled=false。
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.guide.context import GuideContext
from app.agents.guide.long_term import LongTermSummary
from app.db.models import ChildUser

KIND_COMEBACK = "comeback"
KIND_STREAK = "streak"
KIND_WEEKLY = "weekly"

_DEFAULT_STREAK_MILESTONES = (3, 7, 14, 21, 30)


def proactive_enabled(*, profile_state: dict | None = None) -> bool:
    if os.getenv("GUIDE_PROACTIVE_ENABLED", "1").strip() != "1":
        return False
    if isinstance(profile_state, dict) and profile_state.get("enabled") is False:
        return False
    return True


def _streak_milestones() -> tuple[int, ...]:
    raw = os.getenv("GUIDE_PROACTIVE_STREAK_MILESTONES", "").strip()
    if not raw:
        return _DEFAULT_STREAK_MILESTONES
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            n = int(part)
        except ValueError:
            continue
        if n > 0:
            out.append(n)
    return tuple(sorted(set(out))) or _DEFAULT_STREAK_MILESTONES


def _weekly_enabled() -> bool:
    return os.getenv("GUIDE_PROACTIVE_WEEKLY", "1").strip() == "1"


def _iso_week_key(day: date) -> str:
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def _parse_day(s: str) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def load_proactive_state(db: Session, child_user_id: int) -> dict[str, Any]:
    child = db.get(ChildUser, child_user_id)
    if not child or not isinstance(child.profile_json, dict):
        return {}
    blob = child.profile_json.get("guide_proactive")
    return dict(blob) if isinstance(blob, dict) else {}


def save_proactive_state(db: Session, child_user_id: int, state: dict[str, Any]) -> None:
    child = db.get(ChildUser, child_user_id)
    if not child:
        return
    pj = dict(child.profile_json or {})
    pj["guide_proactive"] = state
    child.profile_json = pj
    try:
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(child, "profile_json")
        db.commit()
    except Exception:
        db.rollback()


def _text_comeback(days: int | None) -> str:
    if days is not None and days >= 7:
        return "好久不见也没关系，今天回来练一会儿就好，我们慢慢把节奏找回来。"
    return "这几天没练也没事，今天回来热热身就好，保持轻松节奏最重要。"


def _text_streak(n: int) -> str:
    return f"连续打卡已经 {n} 天了，节奏保持得很好，继续按自己的步子来就行。"


def _text_weekly(lt: LongTermSummary) -> str:
    parts = ["本周小结："]
    if lt.checkins_last_14d > 0:
        parts.append(f"近两周有 {lt.checkins_last_14d} 天练过。")
    else:
        parts.append("近两周练习偏少，有空打开今日训练热热身即可。")
    if lt.preferred_minutes:
        parts.append(f"你常用约 {lt.preferred_minutes} 分钟。")
    if lt.weak_skills:
        # 不提档位/晋级公式，只给温和关注点
        focus = "、".join(lt.weak_skills[:2])
        parts.append(f"近期可多留意「{focus}」，不必焦虑。")
    else:
        parts.append("有疑问随时问我。")
    return "".join(parts)


def _candidate(
    *,
    ctx: GuideContext,
    long_term: LongTermSummary,
    state: dict[str, Any],
) -> dict[str, Any] | None:
    """按优先级选一条；不写库。"""
    day = _parse_day(ctx.training_day) or date.today()

    # 1) 掉队召回
    if ctx.situation == "sparse_return":
        return {
            "kind": KIND_COMEBACK,
            "text": _text_comeback(ctx.days_since_last_checkin),
        }

    # 2) 连续打卡里程碑（今日已有训练进行中/完成时也鼓励）
    streak = int(long_term.checkin_streak or 0)
    milestones = _streak_milestones()
    last_m = int(state.get("last_streak_milestone") or 0)
    hit = max((m for m in milestones if streak >= m), default=0)
    if hit > 0 and hit > last_m and streak >= hit:
        # 未测完天赋时不抢戏
        if ctx.situation != "need_assessment":
            return {
                "kind": KIND_STREAK,
                "text": _text_streak(streak),
                "streak": streak,
                "milestone": hit,
            }

    # 3) 周简报：本周尚未发过，且有一定训练信号
    if _weekly_enabled() and ctx.situation != "need_assessment":
        week = _iso_week_key(day)
        if state.get("last_weekly_iso") != week:
            if long_term.total_checkins > 0 or long_term.checkins_last_14d > 0:
                return {
                    "kind": KIND_WEEKLY,
                    "text": _text_weekly(long_term),
                    "week": week,
                }

    return None


def resolve_proactive(
    db: Session,
    child_user_id: int,
    ctx: GuideContext,
    long_term: LongTermSummary,
    *,
    persist: bool = True,
) -> dict[str, Any] | None:
    """返回 {kind, text, ...}；同训练日复用已展示内容；频控写 profile。"""
    state = load_proactive_state(db, child_user_id)
    if not proactive_enabled(profile_state=state):
        return None

    day = str(ctx.training_day or "")[:10]
    shown = state.get("shown")
    if (
        state.get("shown_day") == day
        and isinstance(shown, dict)
        and shown.get("text")
    ):
        return {
            "kind": shown.get("kind"),
            "text": shown.get("text"),
            "cached": True,
        }

    cand = _candidate(ctx=ctx, long_term=long_term, state=state)
    if not cand:
        return None

    if persist:
        new_state = dict(state)
        new_state["shown_day"] = day
        new_state["shown"] = {
            "kind": cand["kind"],
            "text": cand["text"],
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if cand["kind"] == KIND_STREAK:
            new_state["last_streak_milestone"] = int(
                cand.get("milestone") or cand.get("streak") or 0
            )
        if cand["kind"] == KIND_WEEKLY and cand.get("week"):
            new_state["last_weekly_iso"] = cand["week"]
        # 保留用户关闭开关
        if "enabled" in state:
            new_state["enabled"] = state["enabled"]
        save_proactive_state(db, child_user_id, new_state)

    return {"kind": cand["kind"], "text": cand["text"]}
