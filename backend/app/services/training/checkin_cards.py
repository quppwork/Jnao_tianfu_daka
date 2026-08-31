"""打卡卡片清洗与汇总（纯函数，无 DB 方案依赖）"""

from app.db.models import TrainingPlan, TrainingRecord
from app.services.datetime_fmt import format_cst

def _card_summary(c: dict) -> str:
    name = c.get("name") or ""
    if name == "极速运算":
        return (
            f"{name}({c.get('tag') or '运算'},{c.get('time') or '?'}分钟,"
            f"{c.get('count') or '?'}题,{c.get('accuracy') or '?'}%)"
        )
    if name == "扫描速记":
        material = c.get("materialName") or c.get("bookName") or "?"
        return (
            f"扫描速记：用时{c.get('time') or '?'}分钟，记住{c.get('wordCount') or '?'}字"
            f"《{material}》"
        )
    if name == "超脑阅读":
        words = c.get("wordCount") or c.get("content") or "?"
        return f"超脑阅读({c.get('time') or '?'}分钟,{words}字)"
    if name == "影像追忆":
        words = c.get("wordCount") or c.get("content") or "?"
        return f"影像追忆({c.get('time') or '?'}分钟,{words}字)"
    return f"{name}({c.get('time') or '?'}分钟)"


def _summarize_time_spent(cards: list[dict]) -> str | None:
    parts: list[str] = []
    total = 0.0
    for c in cards or []:
        t = c.get("time")
        if t is None or t == "":
            continue
        try:
            mins = float(t)
        except (TypeError, ValueError):
            continue
        if mins <= 0:
            continue
        total += mins
        name = c.get("name") or "训练"
        parts.append(f"{name}{mins:g}分钟")
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return f"合计{total:g}分钟（{'、'.join(parts)}）"


def _summarize_results(cards: list[dict]) -> str | None:
    parts = [str(c.get("result")).strip() for c in cards or [] if c.get("result")]
    return "；".join(parts) if parts else None


def _summarize_notes(cards: list[dict]) -> str | None:
    parts = [str(c.get("note")).strip() for c in cards or [] if c.get("note")]
    return "；".join(parts) if parts else None


def _sanitize_card(card: dict) -> dict:
    """清洗单张打卡卡片，防止脏数据入库"""
    c = dict(card)
    # 数值字段：转 float 并 clamp 到合理范围
    for field, lo, hi in [
        ("time", 0.5, 480), ("wordCount", 1, 1000000),
        ("accuracy", 0, 100), ("count", 1, 100000),
    ]:
        raw = c.get(field)
        if raw is not None and raw != "":
            try:
                v = float(str(raw))
                c[field] = max(lo, min(hi, v))
            except (ValueError, TypeError):
                c.pop(field, None)
    # 文本字段：截断
    for field, limit in [
        ("note", 2000), ("content", 2000), ("result", 2000),
        ("materialName", 200), ("tag", 50), ("tool", 50),
        ("materialType", 50), ("forwardAcc", 50), ("backwardAcc", 50),
        ("forwardTime", 20), ("backwardTime", 20),
    ]:
        val = c.get(field)
        if isinstance(val, str) and len(val) > limit:
            c[field] = val[:limit]
    return c


def _apply_card_fields_to_record(
    *,
    cards: list[dict] | None,
    ability_type: str | None,
    time_spent: str | None,
    content: str | None,
    result: str | None,
    note: str | None,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    if not cards:
        return ability_type, time_spent, content, result, note
    auto_ability, auto_content = _summarize_cards(cards)
    return (
        ability_type or auto_ability,
        time_spent or _summarize_time_spent(cards),
        content or auto_content,
        result or _summarize_results(cards),
        note or _summarize_notes(cards),
    )


def _summarize_cards(cards: list[dict]) -> tuple[str, str]:
    names = [c.get("name") for c in cards if c.get("name")]
    ability_type = "、".join(names)
    content = "；".join(_card_summary(c) for c in cards if c.get("name"))
    return ability_type, content


def _record_to_dict(record: TrainingRecord, *, plan: TrainingPlan | None = None) -> dict:
    created = record.created_at
    train_date = None
    if record.train_date:
        train_date = record.train_date.isoformat()
    elif plan and plan.plan_date:
        train_date = plan.plan_date.isoformat()
    elif created:
        train_date = created.date().isoformat()
    checkin_at = format_cst(created) if created else None
    cards = record.files_json if isinstance(record.files_json, list) else []
    phase_blocks = sorted({c.get("phaseBlock") for c in cards if c.get("phaseBlock")})
    return {
        "id": record.id,
        "plan_id": record.plan_id,
        "item_id": record.item_id,
        "train_date": train_date,
        "checkin_at": checkin_at,
        "checkin_time": created.strftime("%H:%M") if created else None,
        "ability_type": record.ability_type,
        "time_spent": record.time_spent,
        "content": record.content,
        "result": record.result,
        "note": record.note,
        "attitude_pct": record.attitude_pct,
        "phase_blocks": phase_blocks,
        "cards": cards,
        "created_at": checkin_at,
    }


def group_checkin_history_by_day(items: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for item in items:
        day = item.get("train_date") or (item.get("checkin_at") or "")[:10] or "unknown"
        buckets.setdefault(day, []).append(item)
    out = []
    for d in sorted(buckets.keys(), reverse=True):
        recs = sorted(
            buckets[d],
            key=lambda x: x.get("checkin_at") or "",
            reverse=True,
        )
        out.append({"date": d, "records": recs})
    return out

