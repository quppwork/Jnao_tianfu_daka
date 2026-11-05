"""测评历史保留：首条确认天赋常留 + 其余共最多 10 条。"""

from __future__ import annotations

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChildUser, TalentAssessment, TalentAssessmentArchive
from app.services import assessment_service as svc


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _user(db, phone="13800001111"):
    u = ChildUser(
        parent_phone=phone,
        nickname="学员",
        role="student",
        password_hash="x",
        profile_json={},
    )
    db.add(u)
    db.flush()
    return u


def _add(db, user_id, *, talent="德者", test_type=1, jnao_id: str):
    row = TalentAssessment(
        child_user_id=user_id,
        jnao_record_id=jnao_id,
        answer_bitstring="1" * 35,
        test_type=test_type,
        talent_primary=talent,
        talent_code=svc.resolve_talent_code(talent),
        talent_tag=svc.resolve_talent_tag(svc.resolve_talent_code(talent)),
        report_json={"talent": talent},
    )
    db.add(row)
    db.flush()
    return row


def test_prune_keeps_protected_and_newest():
    db = _db()
    try:
        user = _user(db)
        first = _add(db, user.id, talent="德者", jnao_id="first")
        user.profile_json = {
            "talent_code": first.talent_code,
            "talent_primary": "德者",
            "talent_source": "assessment",
            "latest_assessment_id": first.id,
        }
        db.commit()
        extras = [_add(db, user.id, talent="学者", jnao_id=f"e{i}") for i in range(12)]
        db.commit()
        assert (
            db.scalar(
                select(func.count())
                .select_from(TalentAssessment)
                .where(TalentAssessment.child_user_id == user.id)
            )
            == 13
        )

        out = svc.prune_assessments(db, user.id, keep=10)
        assert out["deleted"] == 3
        assert out["protected_id"] == first.id
        left_ids = {
            r.id
            for r in db.scalars(
                select(TalentAssessment).where(TalentAssessment.child_user_id == user.id)
            ).all()
        }
        assert len(left_ids) == 10
        assert first.id in left_ids
        assert extras[-1].id in left_ids
        assert extras[0].id not in left_ids
        archived = db.scalar(select(func.count()).select_from(TalentAssessmentArchive))
        assert int(archived or 0) >= 3
    finally:
        db.close()


def test_list_assessments_default_cap_10():
    db = _db()
    try:
        user = _user(db, phone="13800002222")
        for i in range(15):
            _add(db, user.id, talent="思者", jnao_id=f"l{i}")
        db.commit()
        items = svc.list_assessments(db, user.id)
        assert len(items) == 10
    finally:
        db.close()


def test_protected_falls_back_to_first_valid():
    db = _db()
    try:
        user = _user(db, phone="13800003333")
        a = _add(db, user.id, talent="德者", jnao_id="a1")
        _add(db, user.id, talent="学者", jnao_id="a2")
        db.commit()
        assert svc.protected_assessment_id(db, user.id) == a.id
    finally:
        db.close()
