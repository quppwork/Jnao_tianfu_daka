"""成长里程碑 — 徽章与时间线（基于真实数据聚合）"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import QaSession, TalentAssessment, TrainingRecord
from app.services.assessment_service import get_latest_assessment
from app.services.qa_service import count_user_messages


def _checkin_count(db: Session, child_user_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
    ) or 0


def get_badges(db: Session, child_user_id: int) -> list[dict]:
    has_assessment = get_latest_assessment(db, child_user_id) is not None
    checkins = _checkin_count(db, child_user_id)
    qa_count = count_user_messages(db, child_user_id)

    defs = [
        ("首次测评", "🌟", "完成天赋测试", has_assessment),
        ("初露锋芒", "🔥", "累计打卡7天", checkins >= 7),
        ("持之以恒", "⚡", "累计打卡30天", checkins >= 30),
        ("百炼成钢", "🏆", "累计打卡100次", checkins >= 100),
        ("全能王者", "👑", "完成全部能力训练", False),
        ("知识达人", "💎", "累计提问100次", qa_count >= 100),
    ]
    return [
        {"name": n, "icon": ic, "cond": c, "earned": earned}
        for n, ic, c, earned in defs
    ]


def get_milestones(db: Session, child_user_id: int) -> list[dict]:
    """荣誉级别达成条件说明"""
    checkins = _checkin_count(db, child_user_id)
    assessment = get_latest_assessment(db, child_user_id)
    return [
        {
            "level": "入门学员",
            "condition": "完成天赋测评",
            "achieved": assessment is not None,
            "talent": assessment.talent_primary if assessment else None,
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
    ]


def get_timeline(db: Session, child_user_id: int, limit: int = 30) -> list[dict]:
    events: list[dict] = []

    assessment = db.scalar(
        select(TalentAssessment)
        .where(TalentAssessment.child_user_id == child_user_id)
        .order_by(TalentAssessment.id.asc())
        .limit(1)
    )
    if assessment:
        d = assessment.assessed_at.date() if assessment.assessed_at else date.today()
        events.append({
            "title": "完成首次天赋测评",
            "date": d.strftime("%m-%d"),
            "desc": f"主导天赋：{assessment.talent_primary or '未知'}",
            "done": True,
            "sort_key": d.isoformat(),
        })

    records = db.scalars(
        select(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
        .order_by(TrainingRecord.id.asc())
    ).all()
    milestones = {1, 7, 10, 30, 100}
    for i, rec in enumerate(records, start=1):
        if i not in milestones:
            continue
        d = rec.created_at.date() if rec.created_at else date.today()
        events.append({
            "title": f"第 {i} 次打卡",
            "date": d.strftime("%m-%d"),
            "desc": "完成今日训练打卡",
            "done": True,
            "sort_key": d.isoformat() + f"-{i:04d}",
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
            "title": "首次学科答疑",
            "date": d.strftime("%m-%d"),
            "desc": "提出第一个学科问题",
            "done": True,
            "sort_key": d.isoformat() + "-qa",
        })

    # future goals
    checkins = len(records)
    if checkins < 30:
        events.append({
            "title": "累计打卡 30 天",
            "date": "未来",
            "desc": "解锁「持之以恒」徽章",
            "done": False,
            "sort_key": "z-future-30",
        })
    if checkins < 100:
        events.append({
            "title": "累计打卡 100 次",
            "date": "未来",
            "desc": "解锁「百炼成钢」金徽章",
            "done": False,
            "sort_key": "z-future-100",
        })

    events.sort(key=lambda e: e["sort_key"])
    for e in events:
        e.pop("sort_key", None)
    return events[:limit]
