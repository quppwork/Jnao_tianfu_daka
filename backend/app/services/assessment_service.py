"""天赋测评持久化"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.talent_mapping import resolve_talent_code, resolve_talent_tag
from app.db.models import TalentAssessment


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
    return record


def get_latest_assessment(db: Session, child_user_id: int) -> TalentAssessment | None:
    return db.scalar(
        select(TalentAssessment)
        .where(TalentAssessment.child_user_id == child_user_id)
        .order_by(TalentAssessment.id.desc())
        .limit(1)
    )


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
