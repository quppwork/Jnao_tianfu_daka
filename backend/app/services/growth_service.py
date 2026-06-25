"""成长里程碑 — 徽章、荣誉级别、时间线、分享（基于真实业务数据聚合）"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ChildUser, ContentItem, QaSession, TalentAssessment, TrainingItem, TrainingPlan, TrainingRecord
from app.services.assessment_service import get_latest_assessment
from app.services.content_meta import parse_item_meta, skill_from_title
from app.services.qa_service import count_user_messages

# 全能王者：至少完成打卡的核心能力课（与课表首屏能力对齐）
MASTERY_SKILLS = ("影像追忆", "扫描速记", "极速学习", "数学奥秘", "英语奥秘")

CHECKIN_MILESTONES = (1, 7, 10, 30, 100)
QA_MILESTONES = (1, 10, 50, 100)


def _checkin_count(db: Session, child_user_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
    ) or 0


def _checkin_dates(db: Session, child_user_id: int) -> list[date]:
    rows = db.scalars(
        select(TrainingPlan.plan_date)
        .join(TrainingRecord, TrainingRecord.plan_id == TrainingPlan.id)
        .where(TrainingPlan.child_user_id == child_user_id)
        .distinct()
        .order_by(TrainingPlan.plan_date.asc())
    ).all()
    return list(rows)


def _checkin_streak(dates: list[date], *, today: date | None = None) -> int:
    if not dates:
        return 0
    today = today or date.today()
    date_set = set(dates)
    # 允许今天未打卡但从昨天起的连续 streak
    start = today if today in date_set else today - timedelta(days=1)
    if start not in date_set:
        return 0
    streak = 0
    cursor = start
    while cursor in date_set:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _trained_skills(db: Session, child_user_id: int) -> set[str]:
    items = db.scalars(
        select(ContentItem)
        .join(TrainingItem, TrainingItem.content_item_id == ContentItem.id)
        .join(TrainingPlan, TrainingPlan.id == TrainingItem.plan_id)
        .where(
            TrainingPlan.child_user_id == child_user_id,
            TrainingItem.checkin_status == "done",
        )
    ).all()
    skills: set[str] = set()
    for item in items:
        meta = parse_item_meta(item)
        skill = meta.get("skill") or skill_from_title(item.lesson_title)
        if skill and skill != "训练":
            skills.add(skill)
    return skills


def _mastery_complete(trained: set[str]) -> bool:
    return all(s in trained for s in MASTERY_SKILLS)


def _collect_stats(db: Session, child_user_id: int) -> dict:
    assessment = get_latest_assessment(db, child_user_id)
    checkins = _checkin_count(db, child_user_id)
    dates = _checkin_dates(db, child_user_id)
    streak = _checkin_streak(dates)
    qa_count = count_user_messages(db, child_user_id)
    trained = _trained_skills(db, child_user_id)
    mastery = _mastery_complete(trained)
    user = db.get(ChildUser, child_user_id)
    return {
        "user": user,
        "assessment": assessment,
        "checkins": checkins,
        "checkin_dates": dates,
        "streak": streak,
        "qa_count": qa_count,
        "trained_skills": trained,
        "mastery": mastery,
    }


def _event_date_str(d: date) -> str:
    return d.strftime("%m-%d")


def get_badges(db: Session, child_user_id: int) -> list[dict]:
    stats = _collect_stats(db, child_user_id)
    trained = stats["trained_skills"]
    mastery = stats["mastery"]
    earned_at_map = _build_earned_at_map(db, child_user_id, stats)

    defs = [
        ("首次测评", "🌟", "完成天赋测试", stats["assessment"] is not None, "assessment"),
        ("初露锋芒", "🔥", "累计打卡 7 次", stats["checkins"] >= 7, "checkin_7"),
        ("持之以恒", "⚡", "累计打卡 30 次", stats["checkins"] >= 30, "checkin_30"),
        ("百炼成钢", "🏆", "累计打卡 100 次", stats["checkins"] >= 100, "checkin_100"),
        ("连续一周", "📅", "连续打卡 7 天", stats["streak"] >= 7, "streak_7"),
        ("答疑新星", "💬", "首次学科提问", stats["qa_count"] >= 1, "qa_1"),
        ("知识达人", "💎", "累计提问 100 次", stats["qa_count"] >= 100, "qa_100"),
        ("全能王者", "👑", "完成全部核心能力训练", mastery, "mastery"),
    ]
    progress_map = {
        "checkin_7": f"{min(stats['checkins'], 7)}/7",
        "checkin_30": f"{min(stats['checkins'], 30)}/30",
        "checkin_100": f"{min(stats['checkins'], 100)}/100",
        "streak_7": f"{min(stats['streak'], 7)}/7",
        "qa_100": f"{min(stats['qa_count'], 100)}/100",
        "mastery": f"{sum(1 for s in MASTERY_SKILLS if s in trained)}/{len(MASTERY_SKILLS)}",
    }
    out = []
    for name, icon, cond, earned, key in defs:
        item = {
            "name": name,
            "icon": icon,
            "cond": cond,
            "earned": earned,
            "earned_at": earned_at_map.get(key) if earned else None,
        }
        if key in progress_map and not earned:
            item["progress"] = progress_map[key]
        out.append(item)
    return out


def _build_earned_at_map(db: Session, child_user_id: int, stats: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    assessment = stats["assessment"]
    if assessment and assessment.assessed_at:
        mapping["assessment"] = assessment.assessed_at.date().isoformat()

    records = db.scalars(
        select(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
        .order_by(TrainingRecord.id.asc())
    ).all()
    for i, rec in enumerate(records, start=1):
        if i == 7:
            mapping["checkin_7"] = _record_date_iso(rec)
        if i == 30:
            mapping["checkin_30"] = _record_date_iso(rec)
        if i == 100:
            mapping["checkin_100"] = _record_date_iso(rec)

    if stats["qa_count"] >= 1:
        first_qa = db.scalar(
            select(QaSession)
            .where(QaSession.child_user_id == child_user_id)
            .order_by(QaSession.id.asc())
            .limit(1)
        )
        if first_qa and first_qa.created_at:
            mapping["qa_1"] = first_qa.created_at.date().isoformat()

    if stats["streak"] >= 7:
        mapping["streak_7"] = date.today().isoformat()

    if stats["mastery"]:
        mapping["mastery"] = date.today().isoformat()

    return mapping


def _record_date_iso(rec: TrainingRecord) -> str:
    if rec.created_at:
        return rec.created_at.date().isoformat()
    return date.today().isoformat()


def get_milestones(db: Session, child_user_id: int) -> list[dict]:
    stats = _collect_stats(db, child_user_id)
    assessment = stats["assessment"]
    checkins = stats["checkins"]
    qa_count = stats["qa_count"]
    trained = stats["trained_skills"]
    mastery = stats["mastery"]

    return [
        {
            "level": "入门学员",
            "condition": "完成天赋测评",
            "achieved": assessment is not None,
            "talent": assessment.talent_primary if assessment else None,
            "progress": "1/1" if assessment else "0/1",
        },
        {
            "level": "坚持训练",
            "condition": "累计打卡 ≥ 7 次",
            "achieved": checkins >= 7,
            "progress": f"{checkins}/7",
        },
        {
            "level": "成长达人",
            "condition": "累计打卡 ≥ 30 次",
            "achieved": checkins >= 30,
            "progress": f"{checkins}/30",
        },
        {
            "level": "百炼学员",
            "condition": "累计打卡 ≥ 100 次",
            "achieved": checkins >= 100,
            "progress": f"{checkins}/100",
        },
        {
            "level": "答疑探索",
            "condition": "累计学科提问 ≥ 1 次",
            "achieved": qa_count >= 1,
            "progress": f"{min(qa_count, 1)}/1",
        },
        {
            "level": "王者之路",
            "condition": "完成全部核心能力训练",
            "achieved": mastery,
            "progress": f"{sum(1 for s in MASTERY_SKILLS if s in trained)}/{len(MASTERY_SKILLS)}",
            "skills_done": sorted(trained & set(MASTERY_SKILLS)),
            "skills_target": list(MASTERY_SKILLS),
        },
    ]


def get_timeline(db: Session, child_user_id: int, limit: int = 40) -> list[dict]:
    events: list[dict] = []
    stats = _collect_stats(db, child_user_id)

    assessment = db.scalar(
        select(TalentAssessment)
        .where(TalentAssessment.child_user_id == child_user_id)
        .order_by(TalentAssessment.id.asc())
        .limit(1)
    )
    if assessment:
        d = assessment.assessed_at.date() if assessment.assessed_at else date.today()
        events.append({
            "type": "assessment",
            "title": "完成首次天赋测评",
            "date": _event_date_str(d),
            "desc": f"主导天赋：{assessment.talent_primary or '未知'}",
            "done": True,
            "sort_key": d.isoformat(),
        })

    records = db.scalars(
        select(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
        .order_by(TrainingRecord.id.asc())
    ).all()
    for i, rec in enumerate(records, start=1):
        if i not in CHECKIN_MILESTONES:
            continue
        d = rec.created_at.date() if rec.created_at else date.today()
        events.append({
            "type": "checkin",
            "title": f"第 {i} 次打卡",
            "date": _event_date_str(d),
            "desc": "完成今日训练打卡",
            "done": True,
            "sort_key": d.isoformat() + f"-c{i:04d}",
        })

    if stats["streak"] >= 7:
        events.append({
            "type": "streak",
            "title": "连续打卡 7 天",
            "date": _event_date_str(date.today()),
            "desc": "养成稳定训练习惯",
            "done": True,
            "sort_key": date.today().isoformat() + "-streak7",
        })

    for skill in sorted(stats["trained_skills"] & set(MASTERY_SKILLS)):
        events.append({
            "type": "skill",
            "title": f"首次完成「{skill}」训练",
            "date": "已达成",
            "desc": "核心能力训练进度 +1",
            "done": True,
            "sort_key": f"skill-{skill}",
        })

    first_qa = db.scalar(
        select(QaSession)
        .where(QaSession.child_user_id == child_user_id)
        .order_by(QaSession.id.asc())
        .limit(1)
    )
    if first_qa:
        d = first_qa.created_at.date() if first_qa.created_at else date.today()
        events.append({
            "type": "qa",
            "title": "首次学科答疑",
            "date": _event_date_str(d),
            "desc": "提出第一个学科问题",
            "done": True,
            "sort_key": d.isoformat() + "-qa1",
        })

    qa_count = stats["qa_count"]
    for n in QA_MILESTONES:
        if n == 1 or qa_count < n:
            continue
        events.append({
            "type": "qa",
            "title": f"累计提问 {n} 次",
            "date": "已达成",
            "desc": "坚持向张宇老师请教",
            "done": True,
            "sort_key": f"qa-milestone-{n:04d}",
        })

    checkins = stats["checkins"]
    future_goals = [
        (30, "累计打卡 30 次", "解锁「持之以恒」徽章"),
        (100, "累计打卡 100 次", "解锁「百炼成钢」金徽章"),
    ]
    if not stats["mastery"]:
        future_goals.append((0, "完成全部核心能力训练", "解锁「全能王者」徽章"))
    for threshold, title, desc in future_goals:
        if threshold and checkins >= threshold:
            continue
        events.append({
            "type": "goal",
            "title": title,
            "date": "未来",
            "desc": desc,
            "done": False,
            "sort_key": f"z-future-{threshold}",
        })

    events.sort(key=lambda e: e["sort_key"])
    for e in events:
        e.pop("sort_key", None)
    return events[:limit]


def get_summary(db: Session, child_user_id: int) -> dict:
    stats = _collect_stats(db, child_user_id)
    badges = get_badges(db, child_user_id)
    earned = sum(1 for b in badges if b["earned"])
    milestones = get_milestones(db, child_user_id)
    honor = "新学员"
    for m in reversed(milestones):
        if m["achieved"]:
            honor = m["level"]
            break

    user = stats["user"]
    assessment = stats["assessment"]
    return {
        "nickname": user.nickname if user else "",
        "talent_primary": assessment.talent_primary if assessment else None,
        "honor_level": honor,
        "total_checkins": stats["checkins"],
        "checkin_streak": stats["streak"],
        "qa_questions": stats["qa_count"],
        "badges_earned": earned,
        "badges_total": len(badges),
        "trained_skills": sorted(stats["trained_skills"]),
        "mastery_skills_done": sorted(stats["trained_skills"] & set(MASTERY_SKILLS)),
        "mastery_skills_target": list(MASTERY_SKILLS),
        "member_since": user.created_at.date().isoformat() if user and user.created_at else None,
    }


def get_share(db: Session, child_user_id: int) -> dict:
    summary = get_summary(db, child_user_id)
    badges = [b for b in get_badges(db, child_user_id) if b["earned"]]
    badge_line = "、".join(b["name"] for b in badges[:5]) or "继续努力中"
    talent = summary["talent_primary"] or "天赋学员"
    lines = [
        f"🌟 {summary['nickname']} 在劲脑天赋成长平台坚持学习啦！",
        f"主导天赋：{talent}",
        f"荣誉级别：{summary['honor_level']}",
        f"累计打卡 {summary['total_checkins']} 次 · 连续 {summary['checkin_streak']} 天",
        f"学科提问 {summary['qa_questions']} 次",
        f"已获徽章：{badge_line}",
        "",
        "一起来打卡训练，遇见更好的自己 ✨",
        "#劲脑天赋 #成长里程碑",
    ]
    text = "\n".join(lines)
    return {
        "title": f"{summary['nickname']}的成长成就",
        "text": text,
        "highlights": [
            f"主导天赋：{talent}",
            f"荣誉级别：{summary['honor_level']}",
            f"累计打卡 {summary['total_checkins']} 次",
            f"已获得 {summary['badges_earned']} 枚徽章",
        ],
    }
