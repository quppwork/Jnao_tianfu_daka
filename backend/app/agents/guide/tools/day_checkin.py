"""工具：某一训练日的打卡内容摘要（只读）。

返回该日已提交打卡的技能与填写字段摘要，不含排课/课件挑选逻辑、不含媒体文件。
支持 date=latest / 最近一次；未指定日期时先查今日，今日无记录则回退最近有打卡的一天。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.agents.guide.tools import register

_MAX_RECORDS = 12
_MAX_CARDS_PER_RECORD = 6
_NOTE_MAX = 80

_LATEST_TOKENS = frozenset({
    "latest", "last", "最近", "最近一次", "上次", "最近一笔", "上一次",
})
_TODAY_TOKENS = frozenset({"today", "今日", "今天"})

# 允许回传给模型的卡片字段（刻意不含 files）
_CARD_KEYS = (
    "name",
    "time",
    "wordCount",
    "result",
    "note",
    "accuracy",
    "count",
    "tag",
    "content",
    "materialName",
    "materialType",
    "tool",
    "phaseBlock",
    "completed",
)


def _clip(val, *, max_len: int = _NOTE_MAX):
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if len(s) > max_len:
        return s[: max_len - 1] + "…"
    return s


def _card_summary(card: dict) -> dict:
    out: dict = {}
    for key in _CARD_KEYS:
        if key not in card:
            continue
        val = card.get(key)
        if val is None or val == "":
            continue
        if key in ("note", "result", "content", "materialName"):
            clipped = _clip(val)
            if clipped is not None:
                out[key] = clipped
        else:
            out[key] = val
    return out


def _record_summary(item: dict) -> dict:
    cards_raw = item.get("cards") if isinstance(item.get("cards"), list) else []
    cards = [
        c
        for c in (_card_summary(x) for x in cards_raw if isinstance(x, dict))
        if c
    ][:_MAX_CARDS_PER_RECORD]
    return {
        "train_date": item.get("train_date"),
        "checkin_time": item.get("checkin_time"),
        "ability_type": item.get("ability_type") or None,
        "time_spent": _clip(item.get("time_spent"), max_len=40),
        "content": _clip(item.get("content"), max_len=120),
        "result": _clip(item.get("result")),
        "note": _clip(item.get("note")),
        "cards": cards,
    }


def _day_key(item: dict) -> str:
    return str(item.get("train_date") or "")[:10]


def _latest_day(items: list[dict]) -> str | None:
    days = sorted(
        {_day_key(it) for it in items if _day_key(it)},
        reverse=True,
    )
    return days[0] if days else None


def _resolve_query_date(
    *,
    args: dict,
    today: date,
    items: list[dict],
) -> tuple[str, str]:
    """返回 (query_date, mode)。

    mode: today | date | latest | latest_fallback
    """
    raw = ""
    if isinstance(args, dict):
        if args.get("latest") in (True, 1, "1", "true", "True"):
            raw = "latest"
        else:
            raw = str(args.get("date") or "").strip()

    if raw.lower() in _LATEST_TOKENS or raw in _LATEST_TOKENS:
        latest = _latest_day(items)
        return (latest or today.isoformat()), "latest"

    if raw in _TODAY_TOKENS:
        return today.isoformat(), "today"

    if raw:
        try:
            return date.fromisoformat(raw[:10]).isoformat(), "date"
        except ValueError:
            pass

    # 未指定：先今日，无记录则回退最近一次
    today_s = today.isoformat()
    if any(_day_key(it) == today_s for it in items):
        return today_s, "today"
    latest = _latest_day(items)
    if latest:
        return latest, "latest_fallback"
    return today_s, "today"


@register("get_day_checkin_detail")
def get_day_checkin_detail(db: Session, child_user_id: int, args: dict) -> dict:
    """按训练日查打卡明细。

    args.date: YYYY-MM-DD | today/今日 | latest/最近一次；省略则今日，今日空则回退最近有打卡日。
    """
    from app.services.dev_clock import resolve_training_now
    from app.services.training_day import get_training_day
    from app.services.training_service import get_checkin_history

    today = get_training_day(resolve_training_now(db, child_user_id))
    items = get_checkin_history(db, child_user_id, limit=80)
    target_s, mode = _resolve_query_date(
        args=args if isinstance(args, dict) else {},
        today=today,
        items=items,
    )

    matched = [
        it for it in items if _day_key(it) == target_s
    ][:_MAX_RECORDS]

    records = [_record_summary(it) for it in matched]
    skills: list[str] = []
    for rec in records:
        name = (rec.get("ability_type") or "").strip()
        if name and name not in skills:
            skills.append(name)
        for card in rec.get("cards") or []:
            cn = (card.get("name") or "").strip()
            if cn and cn not in skills:
                skills.append(cn)

    msg = None
    if not records:
        msg = "该日暂无打卡记录"
    elif mode == "latest_fallback":
        msg = f"今日暂无打卡，已返回最近一次（{target_s}）"

    return {
        "training_day": today.isoformat(),
        "query_date": target_s,
        "mode": mode,
        "is_today": target_s == today.isoformat(),
        "record_count": len(records),
        "skills": skills[:12],
        "records": records,
        "message": msg,
    }
