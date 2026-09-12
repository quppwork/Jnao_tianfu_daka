"""家长端 · 孩子训练看板汇总。

口径（产品确认）：
- 本周时长：有打卡日的计划分钟（无计划则用当日打卡项 duration 合计）
- 本周有效率：本周打卡态度分均值（无态度分则按听完项占比估算）
- 累计值：经验 XP（与中央电脑一致；文案仍可叫累计值）
- 冲段焦虑：近 3 日效率曾 ≥90%，且呈下滑趋势 → 预警
- 十门课进度：一期仍由前端演示稿保留，接口不覆盖
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import ChildUser, TrainingPlan, TrainingRecord
from app.services.growth_tier_period import tier_view

CST = ZoneInfo("Asia/Shanghai")

INSIGHT_SYSTEM = """你是张宇老师的智能体「大宇」，给家长写一段训练看板解读（中文，3-5 句）。
只根据【看板数据】说话，不要编造未给出的数字。
语气温暖、具体、可执行：指出亮点、风险（若有冲段焦虑），并给一条本周建议。
不要输出标题、列表符号过多；可保留一两个加粗重点用 ** ** 包裹。"""

# 无 Redis 时的进程内解读缓存（同进程重复打开不重复打豆包）
_insight_mem: dict[str, tuple[float, dict[str, Any]]] = {}
_INSIGHT_MEM_TTL = 3600.0


def _insight_mem_get(key: str) -> dict[str, Any] | None:
    import time

    row = _insight_mem.get(key)
    if not row:
        return None
    exp, val = row
    if time.time() > exp:
        _insight_mem.pop(key, None)
        return None
    return val


def _insight_mem_set(key: str, val: dict[str, Any], ttl: int) -> None:
    import time

    _insight_mem[key] = (time.time() + max(1, ttl), val)
    if len(_insight_mem) > 256:
        # 粗暴淘汰最旧一半
        for k, _ in sorted(_insight_mem.items(), key=lambda kv: kv[1][0])[:128]:
            _insight_mem.pop(k, None)


def _now_cst() -> datetime:
    return datetime.now(CST)


def _week_monday(today: date) -> date:
    return today - timedelta(days=today.weekday())


def _delta_pct(cur: float, prev: float) -> int | None:
    if prev <= 0:
        return None if cur <= 0 else 100
    return int(round((cur - prev) / prev * 100))


def day_efficiency(records: list[TrainingRecord], plan: TrainingPlan | None) -> float | None:
    """单日学习效率 0-100。优先态度分均值，否则完成项占比。"""
    attitudes = [int(r.attitude_pct) for r in records if r.attitude_pct is not None]
    if attitudes:
        return float(round(sum(attitudes) / len(attitudes), 1))
    if plan and plan.items:
        total = len(plan.items)
        done = sum(1 for it in plan.items if (it.checkin_status or "") == "done")
        if total > 0:
            return float(round(done / total * 100, 1))
    if records:
        return 70.0  # 有打卡无态度分的温和默认
    return None


def compute_anxiety(
    daily_eff: list[tuple[date, float | None]],
    *,
    high_bar: float = 90.0,
) -> dict[str, Any]:
    """冲段焦虑：近 3 日效率里曾 ≥high_bar，且整体下滑。

    daily_eff: 按日期升序的 (date, efficiency|None)，取末尾最多 3 个有值点。
    """
    pts = [(d, e) for d, e in daily_eff if e is not None][-3:]
    if len(pts) < 2:
        return {
            "active": False,
            "level": "off",
            "value": None,
            "delta_pct": None,
            "peak": None,
            "label": "冲段焦虑预警·近3日效率",
        }
    vals = [e for _, e in pts]
    peak = max(vals)
    latest = vals[-1]
    # 从峰值后出现下滑：最新 < 峰值，且峰值曾达高位
    declining = latest < peak and any(
        vals[i] > vals[i + 1] for i in range(len(vals) - 1)
    )
    active = peak >= high_bar and declining and latest < high_bar
    # 也允许仍 ≥90 但连续下滑
    if peak >= high_bar and declining and latest < peak:
        active = True
    first = vals[0]
    delta = _delta_pct(latest, first)
    return {
        "active": active,
        "level": "warn" if active else "ok",
        "value": int(round(latest)),
        "delta_pct": delta,
        "peak": int(round(peak)),
        "label": "冲段焦虑预警·近3日效率",
    }


def _plans_in_range(
    db: Session,
    child_user_id: int,
    start: date,
    end: date,
) -> list[TrainingPlan]:
    return list(
        db.scalars(
            select(TrainingPlan)
            .options(selectinload(TrainingPlan.items))
            .where(
                TrainingPlan.child_user_id == child_user_id,
                TrainingPlan.plan_date >= start,
                TrainingPlan.plan_date <= end,
            )
            .order_by(TrainingPlan.plan_date.asc())
        ).all()
    )


def _records_for_day(db: Session, child_user_id: int, day: date) -> list[TrainingRecord]:
    return list(
        db.scalars(
            select(TrainingRecord).where(
                TrainingRecord.child_user_id == child_user_id,
                TrainingRecord.train_date == day,
            )
        ).all()
    )


def _day_minutes(plan: TrainingPlan | None, records: list[TrainingRecord]) -> int:
    if not records and not (plan and (plan.status or "") == "completed"):
        # 无打卡记录不计分钟
        if not records:
            return 0
    if plan and plan.items:
        done = [it for it in plan.items if (it.checkin_status or "") == "done"]
        s = sum(int(it.duration_min or 0) for it in done)
        if s > 0:
            return s
    if plan and plan.planned_minutes and records:
        return int(plan.planned_minutes)
    return 0


def _week_bundle(
    db: Session,
    child_user_id: int,
    *,
    week_start: date,
    today: date,
) -> dict[str, Any]:
    week_end = week_start + timedelta(days=6)
    prev_start = week_start - timedelta(days=7)
    prev_end = week_start - timedelta(days=1)

    def _agg(start: date, end: date) -> tuple[int, float | None, list[dict]]:
        plans = _plans_in_range(db, child_user_id, start, end)
        by_date = {p.plan_date: p for p in plans}
        minutes_total = 0
        effs: list[float] = []
        bars: list[dict] = []
        cur = start
        while cur <= end and cur <= today:
            plan = by_date.get(cur)
            recs = _records_for_day(db, child_user_id, cur)
            mins = _day_minutes(plan, recs) if recs else 0
            minutes_total += mins
            eff = day_efficiency(recs, plan) if recs else None
            if eff is not None:
                effs.append(eff)
            wd = cur.weekday()
            label = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][wd]
            if cur == today:
                label = "今天"
            bars.append(
                {
                    "date": cur.isoformat(),
                    "label": label,
                    "minutes": mins,
                    "efficiency": eff,
                    "is_today": cur == today,
                    "has_checkin": bool(recs),
                }
            )
            cur += timedelta(days=1)
        avg_eff = round(sum(effs) / len(effs), 1) if effs else None
        return minutes_total, avg_eff, bars

    cur_min, cur_eff, bars = _agg(week_start, min(week_end, today))
    prev_min, prev_eff, _ = _agg(prev_start, prev_end)

    last3: list[tuple[date, float | None]] = []
    for i in range(2, -1, -1):
        d = today - timedelta(days=i)
        hit = next((b for b in bars if b["date"] == d.isoformat()), None)
        if hit is None:
            plans = _plans_in_range(db, child_user_id, d, d)
            plan = plans[0] if plans else None
            recs = _records_for_day(db, child_user_id, d)
            last3.append((d, day_efficiency(recs, plan) if recs else None))
        else:
            last3.append((d, hit.get("efficiency")))

    anxiety = compute_anxiety(last3)

    max_m = max((b["minutes"] for b in bars), default=0) or 1
    for b in bars:
        b["height_pct"] = int(round(b["minutes"] / max_m * 100)) if b["minutes"] else 0

    return {
        "week_minutes": {
            "value": cur_min,
            "delta_pct": _delta_pct(cur_min, prev_min),
            "label": "本周训练时长",
        },
        "week_efficiency": {
            "value": int(round(cur_eff)) if cur_eff is not None else None,
            "delta_pct": (
                _delta_pct(cur_eff, prev_eff)
                if cur_eff is not None and prev_eff is not None
                else None
            ),
            "label": "本周有效率",
        },
        "anxiety": anxiety,
        "week_bars": bars,
        "week_start": week_start.isoformat(),
    }


async def build_insight_text(dashboard: dict[str, Any]) -> str:
    from app.services.doubao_client import chat_completion, is_configured

    child = dashboard.get("child") or {}
    metrics = dashboard.get("metrics") or {}
    anxiety = metrics.get("anxiety") or {}
    bars = dashboard.get("week_bars") or []
    peak_bar = max(bars, key=lambda b: int(b.get("minutes") or 0), default=None)

    facts = [
        f"孩子昵称: {child.get('nickname') or '学员'}",
        f"段位: {dashboard.get('tier', {}).get('duan_label') or '-'}",
        f"本周训练时长: {metrics.get('week_minutes', {}).get('value')} 分钟"
        f"（环比 {metrics.get('week_minutes', {}).get('delta_pct')}%）",
        f"本周有效率: {metrics.get('week_efficiency', {}).get('value')}%"
        f"（环比 {metrics.get('week_efficiency', {}).get('delta_pct')}%）",
        f"累计经验: {metrics.get('xp_total', {}).get('value')}"
        f"（本周变化 {metrics.get('xp_total', {}).get('delta')}）",
        f"冲段焦虑: {'是' if anxiety.get('active') else '否'}"
        f" · 近3日效率 {anxiety.get('value')}%（峰值 {anxiety.get('peak')}%）",
    ]
    if peak_bar and int(peak_bar.get("minutes") or 0) > 0:
        facts.append(
            f"本周峰值日: {peak_bar.get('label')} {peak_bar.get('minutes')} 分钟"
        )
    user_msg = "【看板数据】\n" + "\n".join(facts) + "\n\n请写大宇解读："

    if not is_configured():
        wm = metrics.get("week_minutes", {}).get("value") or 0
        we = metrics.get("week_efficiency", {}).get("value")
        if anxiety.get("active"):
            return (
                f"📌 近3日效率从高位回落（峰值约 {anxiety.get('peak')}% → "
                f"当前 {anxiety.get('value')}%），大宇判断为「冲段焦虑」："
                f"建议三天内不加新关，只做复习巩固。"
                f"本周已练 {wm} 分钟"
                + (f"，有效率 {we}%。" if we is not None else "。")
            )
        return (
            f"📌 本周训练时长 {wm} 分钟"
            + (f"，有效率约 {we}%。" if we is not None else "。")
            + "保持节奏，重要关卡可固定在孩子状态最好的时段。"
        )

    reply = await chat_completion(
        system_prompt=INSIGHT_SYSTEM,
        user_message=user_msg,
        history=[],
        max_tokens=320,
    )
    return (reply or "").strip() or "本周数据已同步，继续保持稳定训练节奏即可。"


def get_dashboard(
    db: Session,
    parent_id: int,
    child_id: int,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    from app.services import parent_service
    from app.services.assessment_service import resolve_effective_talent
    from app.services.growth_console_service import get_console
    from app.services.growth_service import get_tier_brief

    # 绑定校验
    parent_service.get_child_detail(db, parent_id, child_id)

    today = today or _now_cst().date()
    week_start = _week_monday(today)
    child = db.get(ChildUser, child_id)
    nickname = (child.nickname if child else None) or "学员"
    talent = None
    if child and isinstance(child.profile_json, dict):
        talent = child.profile_json.get("talent_primary")
    if not talent:
        talent = (resolve_effective_talent(db, child_id) or {}).get("talent_primary")

    brief = get_tier_brief(db, child_id)
    overall = int(brief.get("overall_tier") or 1)
    tv = tier_view(overall)
    console = get_console(db, child_id)
    xp = console.get("xp") or {}
    ladder = console.get("ladder") or {}
    me = ladder.get("me") or {}

    week = _week_bundle(db, child_id, week_start=week_start, today=today)

    # XP 本周变化：用结果 XP 近似（打卡次数相关）；无则用时长差估
    xp_total = int(xp.get("total_xp") or 0)
    xp_delta = int(round((week["week_minutes"]["value"] or 0) * 0.3))

    talent_char = (str(talent)[0] if talent else "·")
    if talent and len(talent) >= 1:
        for ch in ("赢", "思", "德", "行", "学"):
            if ch in talent:
                talent_char = ch
                break

    children = parent_service.list_children(db, parent_id)

    return {
        "child": {
            "id": child_id,
            "nickname": nickname,
            "talent": talent,
            "talent_char": talent_char,
        },
        "children": [
            {"id": c["id"], "nickname": c.get("nickname") or "学员", "talent": c.get("talent")}
            for c in children
        ],
        "tier": {
            "level": tv["level"],
            "duan_label": tv["duan_label"],
            "rank": me.get("rank"),
            "rank_scope": "local",
            "rank_label": (
                f"本机段位榜 第{me['rank']}名" if me.get("rank") else "本机段位榜"
            ),
        },
        "metrics": {
            "week_minutes": week["week_minutes"],
            "week_efficiency": week["week_efficiency"],
            "xp_total": {
                "value": xp_total,
                "delta": xp_delta,
                "label": "累计经验",
            },
            "anxiety": week["anxiety"],
        },
        "week_bars": week["week_bars"],
        "week_start": week["week_start"],
        "skills_progress": None,  # 十门课一期保留前端演示
        "insight": None,  # 由 async 接口填充
        "sync_hint": "实时更新 · 榜单每天 24:00 刷新",
        "synced_at": _now_cst().isoformat(),
    }


async def get_dashboard_with_insight(
    db: Session,
    parent_id: int,
    child_id: int,
    *,
    today: date | None = None,
    with_insight: bool = True,
) -> dict[str, Any]:
    data = get_dashboard(db, parent_id, child_id, today=today)
    if not with_insight:
        return data
    try:
        from app.core.cache import cache_get_json, cache_set_json, ttl_env
        from app.services.doubao_client import is_configured

        # 解读按孩子+日期缓存，避免每次打开都等豆包
        day = (today or _now_cst().date()).isoformat()
        ck = f"jnao:parent:dash_insight:{parent_id}:{child_id}:{day}"
        ttl = ttl_env("CACHE_TTL_PARENT_INSIGHT", 3600)
        cached = cache_get_json(ck) or _insight_mem_get(ck)
        if isinstance(cached, dict) and cached.get("text"):
            data["insight"] = cached
            return data

        text = await build_insight_text(data)
        insight = {
            "text": text,
            "source": "doubao" if is_configured() else "template",
        }
        data["insight"] = insight
        cache_set_json(ck, insight, ttl)
        _insight_mem_set(ck, insight, ttl)
    except Exception:  # noqa: BLE001
        data["insight"] = {
            "text": "本周数据已同步。可结合时长与效率观察孩子节奏；有波动时先稳巩固再冲关。",
            "source": "fallback",
        }
    return data
