"""中央电脑汇总 — 天梯（本机榜）/ 液晶 / 四境 / 经验条。

第一期：技能墙不做；天梯为本机榜（演示同伴 + 自己），每天 24:00（0 点）刷新戳记。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ChildUser, TrainingItem, TrainingPlan, TrainingRecord
from app.services.growth_tier_period import (
    assign_competition_ranks,
    compute_process_xp,
    compute_result_xp,
    lcd_advice,
    lock_progress,
    tier_view,
    xp_bar,
)

CST = ZoneInfo("Asia/Shanghai")

# 本机榜演示同伴（后续生产改为全站聚合）
_LOCAL_PEERS: tuple[dict[str, Any], ...] = (
    {"name": "李泽言", "level": 2, "talent": "行者"},
    {"name": "王梓涵", "level": 5, "talent": "学者"},
    {"name": "陈思远", "level": 4, "talent": "赢者"},
    {"name": "刘一诺", "level": 8, "talent": "学者"},
    {"name": "赵启铭", "level": 1, "talent": "德者"},
    {"name": "孙可欣", "level": 6, "talent": "思者"},
    {"name": "周子墨", "level": 3, "talent": "思者"},
    {"name": "吴浩然", "level": 7, "talent": "行者"},
    {"name": "郑好", "level": 9, "talent": "赢者"},
    {"name": "林小满", "level": 5, "talent": "德者"},
)


def _now_cst() -> datetime:
    return datetime.now(CST)


def board_refresh_window(now: datetime | None = None) -> dict[str, Any]:
    """榜单每天 24:00 / 0:00（上海）更新。"""
    now = now or _now_cst()
    today_mid = datetime.combine(now.date(), time(0, 0), tzinfo=CST)
    as_of = today_mid
    next_at = today_mid + timedelta(days=1)
    return {
        "as_of": as_of.isoformat(),
        "next_refresh_at": next_at.isoformat(),
        "timezone": "Asia/Shanghai",
        "mode": "local",  # 第一期本机榜；生产改为 national
    }


def _checkin_dates(db: Session, child_user_id: int) -> list[date]:
    rows = db.scalars(
        select(TrainingPlan.plan_date)
        .join(TrainingRecord, TrainingRecord.plan_id == TrainingPlan.id)
        .where(TrainingPlan.child_user_id == child_user_id)
        .distinct()
        .order_by(TrainingPlan.plan_date.asc())
    ).all()
    return list(rows)


def _streak(dates: list[date], *, today: date) -> int:
    if not dates:
        return 0
    date_set = set(dates)
    start = today if today in date_set else today - timedelta(days=1)
    if start not in date_set:
        return 0
    streak = 0
    cursor = start
    while cursor in date_set:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _today_plan(db: Session, child_user_id: int, today: date) -> TrainingPlan | None:
    return db.scalar(
        select(TrainingPlan).where(
            TrainingPlan.child_user_id == child_user_id,
            TrainingPlan.plan_date == today,
        )
    )


def _lcd_block(
    db: Session,
    child_user_id: int,
    *,
    overall_tier: int,
    today: date,
) -> dict[str, Any]:
    dates = _checkin_dates(db, child_user_id)
    streak = _streak(dates, today=today)
    today_checked = today in set(dates)
    total_days = len(dates)

    plan = _today_plan(db, child_user_id, today)
    planned = int(plan.planned_minutes or 0) if plan else 0
    items = list(plan.items) if plan else []
    done_items = [it for it in items if (it.checkin_status or "") == "done"]
    today_min = sum(int(it.duration_min or 0) for it in done_items) or (
        planned if today_checked and planned else 0
    )
    titles = [str(it.title or "").strip() for it in done_items if (it.title or "").strip()]
    today_content = " · ".join(titles[:3]) if titles else ("待闯关" if not today_checked else "已打卡")

    # 简易打分：今日有打卡则用态度均值，否则空
    score = None
    if today_checked:
        recs = db.scalars(
            select(TrainingRecord).where(
                TrainingRecord.child_user_id == child_user_id,
                TrainingRecord.train_date == today,
            )
        ).all()
        attitudes = [int(r.attitude_pct) for r in recs if r.attitude_pct is not None]
        if attitudes:
            score = round(sum(attitudes) / len(attitudes))

    from app.services.child_training_state import (
        REQUIRED_SKILLS,
        get_skills_with_records,
        get_training_progress,
    )

    user = db.get(ChildUser, child_user_id)
    state = get_training_progress(user) if user else {}
    with_records = get_skills_with_records(db, child_user_id) if user else set()
    lit = sum(
        1
        for sk in REQUIRED_SKILLS
        if sk in with_records and int((state.get("skills") or {}).get(sk, {}).get("tier") or 1) >= 1
    )

    advice = lcd_advice(streak=streak, today_checked=today_checked, total_days=total_days)
    return {
        "today_minutes": today_min if today_min else None,
        "today_minutes_label": f"{today_min} MIN" if today_min else "未开始",
        "today_content": today_content,
        "today_score": score,
        "today_score_label": f"{score} / 100" if score is not None else "— —",
        "today_checked": today_checked,
        "total_checkin_days": total_days,
        "streak_days": streak,
        "lit_skills": lit,
        "lit_skills_total": len(REQUIRED_SKILLS),
        "advice": advice,
        "online": True,
    }


def _xp_from_history(db: Session, child_user_id: int) -> tuple[float, float]:
    """过程 XP：有打卡的训练日 × 当日规划分钟；结果 XP：打卡记录条数近似达标贡献。"""
    plans = db.scalars(
        select(TrainingPlan)
        .join(TrainingRecord, TrainingRecord.plan_id == TrainingPlan.id)
        .where(TrainingPlan.child_user_id == child_user_id)
        .distinct()
    ).all()
    planned_list = [int(p.planned_minutes or 0) for p in plans]
    process = compute_process_xp(planned_list)

    # 结果：每条已审核打卡记一次「过程结果」贡献（升段仍由 mastery 决定）
    pass_count = db.scalar(
        select(func.count())
        .select_from(TrainingRecord)
        .where(
            TrainingRecord.child_user_id == child_user_id,
            TrainingRecord.review_status == "approved",
        )
    ) or 0
    result = compute_result_xp(int(pass_count))
    return process, result


def _local_ladder(
    *,
    my_name: str,
    my_level: int,
    my_talent: str | None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = [
        {
            "name": p["name"],
            "level": int(p["level"]),
            "talent": p.get("talent"),
            "me": False,
            "duan_label": tier_view(int(p["level"]))["duan_label"],
            "duan_short": tier_view(int(p["level"]))["duan_short"],
        }
        for p in _LOCAL_PEERS
    ]
    rows.append(
        {
            "name": my_name or "我",
            "level": my_level,
            "talent": my_talent,
            "me": True,
            "duan_label": tier_view(my_level)["duan_label"],
            "duan_short": tier_view(my_level)["duan_short"],
        }
    )
    ranked = assign_competition_ranks(rows, score_key="level")
    me = next(r for r in ranked if r.get("me"))
    top10 = ranked[:10]
    total = len(ranked)
    # 超过 X%：严格低于我段位的人数 / (总人数-1)
    below = sum(1 for r in ranked if int(r.get("level") or 0) < int(me.get("level") or 0))
    beat_pct = round(below / max(total - 1, 1) * 100) if total > 1 else 100
    return {
        "me": {
            **me,
            "beat_percent": max(0, min(100, beat_pct)),
            "subtitle": f"我的超脑段位 · 超过本机榜 {max(0, min(100, beat_pct))}% 的学员",
        },
        "top10": top10,
        "total_on_board": total,
        "refresh": board_refresh_window(),
    }


def _month_training_block(
    db: Session,
    child_user_id: int,
    *,
    today: date,
    xp: dict[str, Any],
) -> dict[str, Any]:
    """本月训练日历：有打卡日的规划分钟 + 有效率（态度分均值）。"""
    y, m = today.year, today.month
    month_start = date(y, m, 1)
    if m == 12:
        month_end = date(y + 1, 1, 1)
    else:
        month_end = date(y, m + 1, 1)

    plans = db.scalars(
        select(TrainingPlan).where(
            TrainingPlan.child_user_id == child_user_id,
            TrainingPlan.plan_date >= month_start,
            TrainingPlan.plan_date < month_end,
        )
    ).all()
    plan_ids = [p.id for p in plans]
    records_by_plan: dict[int, list[TrainingRecord]] = {}
    if plan_ids:
        recs = db.scalars(
            select(TrainingRecord).where(
                TrainingRecord.child_user_id == child_user_id,
                TrainingRecord.plan_id.in_(plan_ids),
            )
        ).all()
        for r in recs:
            if r.plan_id is None:
                continue
            records_by_plan.setdefault(int(r.plan_id), []).append(r)

    days_out: list[dict[str, Any]] = []
    rate_acc: list[int] = []
    mins_total = 0
    for p in plans:
        recs = records_by_plan.get(int(p.id), [])
        if not recs:
            continue
        minutes = int(p.planned_minutes or 0)
        if not minutes:
            items = list(p.items) if p.items else []
            minutes = sum(
                int(it.duration_min or 0)
                for it in items
                if (it.checkin_status or "") == "done"
            )
        attitudes = [int(r.attitude_pct) for r in recs if r.attitude_pct is not None]
        rate = round(sum(attitudes) / len(attitudes)) if attitudes else 100
        days_out.append(
            {
                "date": p.plan_date.isoformat() if p.plan_date else "",
                "minutes": minutes,
                "rate": rate,
            }
        )
        mins_total += minutes
        rate_acc.append(rate)

    days_out.sort(key=lambda d: d["date"])
    month_rate = round(sum(rate_acc) / len(rate_acc)) if rate_acc else 0
    return {
        "year": y,
        "month": m,
        "days": days_out,
        "month_minutes": mins_total,
        "month_rate": month_rate,
        "checkin_days": len(days_out),
        "xp_total": int(xp.get("total_xp") or 0),
        "bar_pct": float(xp.get("bar_pct") or 0),
    }


def _practice_realm(*, days_30: int) -> dict[str, Any]:
    """近 30 天打卡天数 → 修行五境（回放舱底栏）。"""
    if days_30 <= 2:
        idx, name = 1, "完全荒废"
    elif days_30 <= 7:
        idx, name = 2, "三天打鱼"
    elif days_30 <= 14:
        idx, name = 3, "尽力训练"
    elif days_30 <= 21:
        idx, name = 4, "锋芒初现"
    else:
        idx, name = 5, "万法归一"
    return {
        "index": idx,
        "label": f"第{['', '一', '二', '三', '四', '五'][idx]}境",
        "name": name,
        "full": f"第{['', '一', '二', '三', '四', '五'][idx]}境·{name}",
        "days_30": days_30,
    }


# 回放舱场景：5 项必修 → 镜头 key
_REPLAY_SCENE_BY_SKILL: dict[str, str] = {
    "超脑阅读": "read",
    "影像追忆": "memory",
    "扫描速记": "read",
    "极速运算": "calc",
    "极速学习": "calc",
}


def _replay_block(
    db: Session,
    child_user_id: int,
    *,
    today: date,
    overall_tier: int,
    xp: dict[str, Any],
    brief: dict[str, Any],
) -> dict[str, Any]:
    """修行回放舱：真实技能段位 / 达标文案 / 修行境。"""
    from app.services.child_training_state import (
        REQUIRED_SKILLS,
        get_skills_with_records,
    )

    dates = _checkin_dates(db, child_user_id)
    days_30 = sum(1 for d in dates if 0 <= (today - d).days < 30)
    realm = _practice_realm(days_30=days_30)
    advance_pass = int(brief.get("advance_pass") or 3)
    with_records = get_skills_with_records(db, child_user_id)
    skills_brief = brief.get("skills") or []
    by_name = {s.get("name"): s for s in skills_brief if isinstance(s, dict)}

    scenes: list[dict[str, Any]] = []
    for sk in REQUIRED_SKILLS:
        sd = by_name.get(sk) or {}
        tier = int(sd.get("tier") or 1)
        consec = int(sd.get("consecutive_pass") or 0)
        active = bool(sd.get("active") if "active" in sd else sk in with_records)
        # 完成度：本段连续达标进度；已练未达标也给基础进度
        if not active:
            pct = 0
            status = "今日未开练"
        else:
            pct = min(100, int(round(consec / max(advance_pass, 1) * 100)))
            if consec >= advance_pass:
                pct = 100
            status = f"段位{tier} · 连续达标 {consec}/{advance_pass}"
        rule = str(sd.get("rule_text") or "").strip()
        if not active:
            meta = f"{sk} · 今日未开练"
        elif rule:
            meta = f"{sk} · 完成度 {pct}% · {rule}"
        else:
            meta = f"{sk} · 完成度 {pct}%"
        scenes.append(
            {
                "skill": sk,
                "scene_key": _REPLAY_SCENE_BY_SKILL.get(sk, "read"),
                "title": sk,
                "tier": tier,
                "consecutive_pass": consec,
                "advance_pass": advance_pass,
                "active": active,
                "pct": pct,
                "status": status,
                "rule_text": rule,
                "meta": meta,
            }
        )

    # 练过的排前；未练垫后
    scenes.sort(key=lambda s: (-int(s["pct"]), -int(s["active"]), s["skill"]))
    tv = tier_view(overall_tier)
    state_line = (
        f"{realm['full']} · Lv.{tv['level']} · 经验 {int(xp.get('total_xp') or 0)}"
    )
    return {
        "realm": realm,
        "state_line": state_line,
        "scenes": scenes,
        "talent": None,  # 不再展示旧天赋值
        "level": tv["level"],
        "duan_label": tv["duan_label"],
        "xp_total": int(xp.get("total_xp") or 0),
    }


def get_console(db: Session, child_user_id: int) -> dict[str, Any]:
    """中央电脑一页汇总。"""
    from app.services.assessment_service import resolve_effective_talent
    from app.services.growth_service import get_tier_brief

    today = _now_cst().date()
    brief = get_tier_brief(db, child_user_id)
    overall_tier = int(brief.get("overall_tier") or 1)
    tv = tier_view(overall_tier)

    user = db.get(ChildUser, child_user_id)
    nickname = (user.nickname if user else None) or "学员"
    talent = None
    if user and isinstance(user.profile_json, dict):
        talent = user.profile_json.get("talent_primary")
    if not talent:
        talent = (resolve_effective_talent(db, child_user_id) or {}).get("talent_primary")

    process_xp, result_xp = _xp_from_history(db, child_user_id)
    xp = xp_bar(process_xp=process_xp, result_xp=result_xp, overall_tier=overall_tier)
    lcd = _lcd_block(db, child_user_id, overall_tier=overall_tier, today=today)
    lcd["xp"] = xp
    lcd["current_label"] = f"Lv.{tv['level']} · {tv['duan_label']}"

    locks = lock_progress(overall_tier)
    ladder = _local_ladder(my_name=nickname, my_level=tv["level"], my_talent=talent)
    month = _month_training_block(db, child_user_id, today=today, xp=xp)
    replay = _replay_block(
        db,
        child_user_id,
        today=today,
        overall_tier=overall_tier,
        xp=xp,
        brief=brief,
    )

    return {
        "tier": {
            **tv,
            "honor_level": brief.get("honor_level"),
            "title": brief.get("title"),
            "advance_pass": brief.get("advance_pass"),
            "skills": brief.get("skills") or [],
        },
        "xp": xp,
        "lcd": lcd,
        "locks": locks,
        "ladder": ladder,
        "month": month,
        "replay": replay,
        "skills_wall": None,
        "energy": {
            "value": int(xp["total_xp"]),
            "label": str(int(xp["total_xp"])),
        },
    }
