# -*- coding: utf-8 -*-
"""profile_json 合并与引导/onboarding 天赋同步"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("JNAO_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.db.models import ChildUser
from app.db.session import get_session_factory, init_db
from app.services.assessment_service import sync_child_user_talent
from app.services.user_service import merge_profile_json, profile_to_dict, update_profile


def test_merge_profile_json_preserves_role_and_onboarding():
    merged = merge_profile_json(
        {"role": "student", "grade": "四年级"},
        {"onboarding": {"student_type": "new", "completed_at": "2026-06-28T10:00:00Z"}},
    )
    assert merged["role"] == "student"
    assert merged["grade"] == "四年级"
    assert merged["onboarding"]["student_type"] == "new"

    merged2 = merge_profile_json(
        {"role": "student", "onboarding": {"student_type": "new"}},
        {"onboarding": {"self_reported_talent": "学者", "self_reported_talent_code": 1}},
    )
    assert merged2["role"] == "student"
    assert merged2["onboarding"]["student_type"] == "new"
    assert merged2["onboarding"]["self_reported_talent"] == "学者"


def test_onboarding_talent_name_only_resolves_code():
    init_db()
    db = get_session_factory()()
    user = ChildUser(parent_phone="13800008888", nickname="name_only")
    db.add(user)
    db.commit()
    db.refresh(user)

    update_profile(
        db,
        user.id,
        profile_json={
            "onboarding": {
                "student_type": "new",
                "completed_at": "2026-06-28T10:00:00Z",
                "self_reported_talent": "学者",
                "talent_unknown": False,
            },
        },
    )
    sync_child_user_talent(db, user.id)
    assert get_self_reported_talent_code(db, user.id) == 1
    entry = __import__("app.services.training_service", fromlist=["get_training_entry"]).get_training_entry(db, user.id)
    assert entry["has_assessment"] and not entry["needs_assessment"]
    db.close()
    init_db()
    db = get_session_factory()()
    user = ChildUser(parent_phone="13800009999", nickname="onb")
    db.add(user)
    db.commit()
    db.refresh(user)

    update_profile(
        db,
        user.id,
        profile_json={
            "role": "student",
            "onboarding": {
                "student_type": "new",
                "completed_at": "2026-06-28T10:00:00Z",
                "self_reported_talent": "学者",
                "self_reported_talent_code": 1,
                "talent_unknown": False,
            },
        },
    )
    sync_child_user_talent(db, user.id)
    db.refresh(user)

    data = profile_to_dict(user, db)
    assert user.training_level == "学者"
    assert data["talent_primary"] == "学者"
    assert data["talent_code"] == 1
    assert data["talent_source"] == "onboarding"
    assert data["onboarding_completed"] is True
    db.close()


def test_onboarding_talent_name_only_resolves_code():
    from app.services.assessment_service import get_self_reported_talent_code
    from app.services.training_service import get_training_entry

    init_db()
    db = get_session_factory()()
    user = ChildUser(parent_phone="13800008888", nickname="name_only")
    db.add(user)
    db.commit()
    db.refresh(user)

    update_profile(
        db,
        user.id,
        profile_json={
            "onboarding": {
                "student_type": "new",
                "completed_at": "2026-06-28T10:00:00Z",
                "self_reported_talent": "学者",
                "talent_unknown": False,
            },
        },
    )
    sync_child_user_talent(db, user.id)
    assert get_self_reported_talent_code(db, user.id) == 1
    entry = get_training_entry(db, user.id)
    assert entry["has_assessment"] and not entry["needs_assessment"]
    db.close()


def test_repair_onboarding_conflicting_unknown_flag():
    from app.services.assessment_service import get_self_reported_talent_code, repair_onboarding_talent
    from app.services.training_service import get_training_entry

    init_db()
    db = get_session_factory()()
    user = ChildUser(parent_phone="13800007777", nickname="dirty")
    db.add(user)
    db.commit()
    db.refresh(user)

    update_profile(
        db,
        user.id,
        profile_json={
            "onboarding": {
                "student_type": "new",
                "completed_at": "2026-06-29T06:00:00Z",
                "talent_unknown": True,
                "self_reported_talent": None,
                "self_reported_talent_code": 1,
            },
        },
    )
    sync_child_user_talent(db, user.id)
    db.refresh(user)
    assert get_self_reported_talent_code(db, user.id) == 1
    entry = get_training_entry(db, user.id)
    assert entry["has_assessment"] and not entry["needs_assessment"]
    ob = user.profile_json["onboarding"]
    assert ob["self_reported_talent"] == "学者"
    assert ob["talent_unknown"] is False
    db.close()
