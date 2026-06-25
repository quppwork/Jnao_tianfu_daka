"""天赋测评持久化"""

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.talent_mapping import resolve_talent_code, resolve_talent_tag
from app.db.models import ChildUser, TalentAssessment, TalentAssessmentArchive

class AssessmentError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _assessment_snapshot(row: TalentAssessment) -> dict:
    return {
        "id": row.id,
        "child_user_id": row.child_user_id,
        "jnao_record_id": row.jnao_record_id,
        "answer_bitstring": row.answer_bitstring,
        "test_type": row.test_type,
        "talent_primary": row.talent_primary,
        "talent_tag": row.talent_tag,
        "talent_code": row.talent_code,
        "report_json": row.report_json,
        "assessed_at": row.assessed_at.isoformat() if row.assessed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def save_assessment(
    db: Session,
    *,
    child_user_id: int,
    jnao_record_id: str,
    answer_bitstring: str,
    test_type: int,
    report: dict,
) -> TalentAssessment:
    talent_primary = report.get("talent") or report.get("check_talent")
    talent_code = resolve_talent_code(talent_primary)
    talent_tag = resolve_talent_tag(talent_code)

    assessed_at = datetime.now(timezone.utc)
    if report.get("create_time"):
        try:
            raw = str(report["create_time"])
            if len(raw) > 10:
                assessed_at = datetime.strptime(raw[:16], "%Y-%m-%d %H:%M")
            else:
                assessed_at = datetime.strptime(raw[:10], "%Y-%m-%d").replace(
                    hour=assessed_at.hour,
                    minute=assessed_at.minute,
                )
        except ValueError:
            pass

    record = TalentAssessment(
        child_user_id=child_user_id,
        jnao_record_id=str(jnao_record_id),
        answer_bitstring=answer_bitstring,
        test_type=test_type,
        talent_primary=talent_primary,
        talent_tag=talent_tag,
        talent_code=talent_code,
        report_json=report,
        assessed_at=assessed_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    sync_child_user_talent(db, child_user_id)
    from app.services.training_service import refresh_today_plan_if_talent_changed

    refresh_today_plan_if_talent_changed(db, child_user_id, assessment=record)
    db.refresh(record)
    return record


def get_latest_assessment(db: Session, child_user_id: int) -> TalentAssessment | None:
    """取孩子用户最新一次天赋测评（按测评时间，其次 id）"""
    return db.scalar(
        select(TalentAssessment)
        .where(TalentAssessment.child_user_id == child_user_id)
        .order_by(TalentAssessment.assessed_at.desc(), TalentAssessment.id.desc())
        .limit(1)
    )


def sync_child_user_talent(db: Session, child_user_id: int) -> None:
    """将 child_user 上的天赋字段同步为最新测评结果"""
    user = db.get(ChildUser, child_user_id)
    if not user:
        return
    latest = get_latest_assessment(db, child_user_id)
    profile = dict(user.profile_json or {})
    if latest and latest.talent_code:
        user.training_level = latest.talent_primary
        profile.update(
            {
                "talent_code": latest.talent_code,
                "talent_tag": latest.talent_tag,
                "talent_primary": latest.talent_primary,
                "latest_assessment_id": latest.id,
            }
        )
    else:
        user.training_level = None
        for key in ("talent_code", "talent_tag", "talent_primary", "latest_assessment_id"):
            profile.pop(key, None)
    user.profile_json = profile
    db.commit()


def list_assessments(db: Session, child_user_id: int, limit: int = 30) -> list[dict]:
    rows = db.scalars(
        select(TalentAssessment)
        .where(TalentAssessment.child_user_id == child_user_id)
        .order_by(TalentAssessment.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "talent": r.talent_primary,
            "talent_primary": r.talent_primary,
            "talent_tag": r.talent_tag,
            "create_time": (
                r.assessed_at.strftime("%Y-%m-%d %H:%M")
                if r.assessed_at
                else (r.report_json or {}).get("create_time")
            ),
            "assessed_at": r.assessed_at.isoformat() if r.assessed_at else None,
        }
        for r in rows
    ]


def get_assessment_by_id(db: Session, assessment_id: int, child_user_id: int) -> TalentAssessment | None:
    row = db.get(TalentAssessment, assessment_id)
    if not row or row.child_user_id != child_user_id:
        return None
    return row


def delete_assessment(db: Session, assessment_id: int, child_user_id: int) -> dict:
    """删除测评：先归档快照，再从主表删除"""
    row = get_assessment_by_id(db, assessment_id, child_user_id)
    if not row:
        raise AssessmentError("测评记录不存在", 404)

    db.add(
        TalentAssessmentArchive(
            original_id=row.id,
            child_user_id=row.child_user_id,
            snapshot_json=_assessment_snapshot(row),
            deleted_at=datetime.now(timezone.utc),
        )
    )
    db.delete(row)
    db.commit()
    sync_child_user_talent(db, child_user_id)
    from app.services.training_service import refresh_today_plan_if_talent_changed

    refresh_today_plan_if_talent_changed(db, child_user_id)
    return {"deleted": True, "assessment_id": assessment_id}
