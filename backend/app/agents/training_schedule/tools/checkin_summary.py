"""排课用打卡/节奏摘要 — 按技能聚合，不暴露 consecutive_pass / 晋级公式。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import TrainingPlan, TrainingRecord
from app.services.training_day import get_training_day
from app.services.dev_clock import resolve_training_now


def _checkin_streak(dates: list[date], *, today: date) -> int:
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


def _gap_days(dates: list[date], *, today: date) -> int:
    """距最近一次打卡的间隔天数；今日有打卡则为 0。"""
    if not dates:
        return -1  # 无历史
    latest = max(dates)
    return max(0, (today - latest).days)


def _parse_train_date(raw: Any) -> date | None:
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return date.fromisoformat(raw.strip()[:10])
        except ValueError:
            return None
    return None


def build_rhythm_summary(
    db: Session,
    child_user_id: int,
    *,
    lookback_days: int = 14,
) -> dict[str, Any]:
    """连打 / 断档 + 近史方案完成度（项数）。"""
    now = resolve_training_now(db, child_user_id)
    today = get_training_day(now)
    since = today - timedelta(days=max(1, lookback_days) - 1)

    date_rows = db.scalars(
        select(TrainingRecord.train_date)
        .where(
            TrainingRecord.child_user_id == child_user_id,
            TrainingRecord.train_date.is_not(None),
        )
        .distinct()
    ).all()
    all_dates = [d for d in date_rows if isinstance(d, date)]
    streak = _checkin_streak(all_dates, today=today)
    gap = _gap_days(all_dates, today=today)

    plans = db.scalars(
        select(TrainingPlan)
        .options(selectinload(TrainingPlan.items))
        .where(TrainingPlan.child_user_id == child_user_id)
        .where(TrainingPlan.plan_date >= since)
        .where(TrainingPlan.plan_date <= today)
        .order_by(TrainingPlan.plan_date.desc())
    ).all()

    completion_days: list[dict[str, Any]] = []
    for p in plans:
        items = list(p.items or [])
        total = len(items)
        if total <= 0:
            continue
        done = sum(1 for it in items if (it.checkin_status or "") == "done")
        completion_days.append({
            "date": str(p.plan_date),
            "planned_minutes": p.planned_minutes,
            "items_total": total,
            "items_done": done,
            "completion_ratio": round(done / total, 2) if total else 0.0,
            "status": p.status,
        })

    ratios = [d["completion_ratio"] for d in completion_days]
    avg_completion = round(sum(ratios) / len(ratios), 2) if ratios else None

    return {
        "lookback_days": lookback_days,
        "checkin_streak_days": streak,
        "days_since_last_checkin": gap,
        "has_checkin_history": bool(all_dates),
        "recent_plan_completion": completion_days[:14],
        "avg_completion_ratio": avg_completion,
        "hint": (
            "连打高可正常推进；断档多天宜先巩固易完成项；"
            "completion_ratio 长期偏低说明计划可能偏满。"
            "勿向用户讲解内部晋级计数。"
        ),
    }


def build_checkin_skill_summary(
    db: Session,
    child_user_id: int,
    *,
    days: int = 14,
    skill_tiers: dict[str, int] | None = None,
    grade_band: str = "primary_low",
) -> dict[str, Any]:
    """近 N 天按技能的打卡质量摘要（达标倾向 / 用时 / 正确率 / 配合度）。"""
    from app.services.content_meta import skill_from_title
    from app.services.training_mastery import evaluate_card
    from app.services.training_service import get_checkin_history

    days = max(1, min(int(days), 30))
    now = resolve_training_now(db, child_user_id)
    today = get_training_day(now)
    since = today - timedelta(days=days - 1)
    skill_tiers = skill_tiers or {}

    items = get_checkin_history(db, child_user_id, limit=80)
    # skill -> aggregates
    agg: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "attempts": 0,
        "passed": 0,
        "failed": 0,
        "unknown": 0,
        "accuracy_sum": 0.0,
        "accuracy_n": 0,
        "time_sum": 0.0,
        "time_n": 0,
        "attitude_sum": 0.0,
        "attitude_n": 0,
        "last_date": None,
    })

    for item in items:
        td = _parse_train_date(item.get("train_date"))
        if td is None or td < since:
            continue
        cards = item.get("cards") if isinstance(item.get("cards"), list) else []
        attitude = item.get("attitude_pct")
        if not cards:
            # 无卡片时尝试从 content/ability 推断技能名
            sk = skill_from_title(str(item.get("content") or item.get("ability_type") or ""))
            if sk:
                a = agg[sk]
                a["attempts"] += 1
                a["unknown"] += 1
                if attitude is not None:
                    try:
                        a["attitude_sum"] += float(attitude)
                        a["attitude_n"] += 1
                    except (TypeError, ValueError):
                        pass
                if a["last_date"] is None or str(td) > str(a["last_date"]):
                    a["last_date"] = str(td)
            continue

        for card in cards:
            if not isinstance(card, dict):
                continue
            sk = str(card.get("name") or "").strip() or skill_from_title(
                str(card.get("materialName") or "")
            )
            if not sk:
                continue
            a = agg[sk]
            a["attempts"] += 1
            if a["last_date"] is None or str(td) > str(a["last_date"]):
                a["last_date"] = str(td)

            tier = int(skill_tiers.get(sk) or 1)
            try:
                ev = evaluate_card(sk, tier, grade_band, card)
                if ev.get("passed"):
                    a["passed"] += 1
                else:
                    # 有阈值且未过 → fail；无填写导致未过也算 fail 倾向
                    a["failed"] += 1
            except Exception:
                a["unknown"] += 1

            acc = card.get("accuracy")
            if acc is None:
                acc = card.get("accuracy_pct")
            if acc is not None:
                try:
                    a["accuracy_sum"] += float(acc)
                    a["accuracy_n"] += 1
                except (TypeError, ValueError):
                    pass
            tmin = card.get("time")
            if tmin is None:
                tmin = card.get("minutes")
            if tmin is not None:
                try:
                    a["time_sum"] += float(tmin)
                    a["time_n"] += 1
                except (TypeError, ValueError):
                    pass
            if attitude is not None:
                try:
                    a["attitude_sum"] += float(attitude)
                    a["attitude_n"] += 1
                except (TypeError, ValueError):
                    pass

    skills_out: list[dict[str, Any]] = []
    for sk, a in sorted(agg.items(), key=lambda x: (-x[1]["attempts"], x[0])):
        attempts = int(a["attempts"])
        passed = int(a["passed"])
        failed = int(a["failed"])
        judged = passed + failed
        pass_rate = round(passed / judged, 2) if judged else None
        entry: dict[str, Any] = {
            "skill": sk,
            "attempts": attempts,
            "passed": passed,
            "failed": failed,
            "pass_rate": pass_rate,
            "last_date": a["last_date"],
        }
        if a["accuracy_n"]:
            entry["avg_accuracy_pct"] = round(a["accuracy_sum"] / a["accuracy_n"], 1)
        if a["time_n"]:
            entry["avg_time_min"] = round(a["time_sum"] / a["time_n"], 1)
        if a["attitude_n"]:
            entry["avg_attitude_pct"] = round(a["attitude_sum"] / a["attitude_n"], 1)
        # 给模型的软标签，不暴露内部计数名
        if pass_rate is not None:
            if pass_rate >= 0.7:
                entry["form"] = "stable"
            elif pass_rate >= 0.4:
                entry["form"] = "mixed"
            else:
                entry["form"] = "struggling"
        else:
            entry["form"] = "unknown"
        skills_out.append(entry)

    struggling = [s["skill"] for s in skills_out if s.get("form") == "struggling"]
    stable = [s["skill"] for s in skills_out if s.get("form") == "stable"]

    return {
        "days": days,
        "skills": skills_out,
        "struggling_skills": struggling,
        "stable_skills": stable,
        "hint": (
            "struggling 宜巩固或少堆难度；stable 可适当后置。"
            "仅作排课参考，勿复述达标阈值或晋级规则。"
        ),
    }
