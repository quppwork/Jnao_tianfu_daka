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

    assessed_at = None
    if report.get("create_time"):
        try:
            assessed_at = datetime.strptime(str(report["create_time"])[:10], "%Y-%m-%d")
        except ValueError:
            assessed_at = datetime.now(timezone.utc)
    else:
        assessed_at = datetime.now(timezone.utc)

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
