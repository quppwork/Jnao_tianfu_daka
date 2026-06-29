# -*- coding: utf-8 -*-
"""onboarding 老学员注册 — 对齐 docs/前端后端API文档.md"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("JNAO_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.db.models import ChildUser
from app.db.session import get_session_factory, init_db
from app.services.assessment_service import sync_child_user_talent
from app.services.onboarding_service import OnboardingError, normalize_onboarding
from app.services.user_service import merge_profile_json, profile_to_dict, update_profile


def test_returning_step3_talent_sync():
    init_db()
    db = get_session_factory()()
    user = ChildUser(parent_phone="13800001001", nickname="ret3")
    db.add(user)
    db.commit()
    db.refresh(user)

    update_profile(
        db,
        user.id,
        profile_json={
            "onboarding": {
                "student_type": "returning",
                "self_reported_talent": "学者",
                "self_reported_talent_code": 1,
                "talent_unknown": False,
            },
        },
    )
    sync_child_user_talent(db, user.id)
    db.refresh(user)

    assert user.training_level == "学者"
    ob = user.profile_json["onboarding"]
    assert ob["talent_unknown"] is False
    assert ob["self_reported_talent_code"] == 1
    data = profile_to_dict(user, db)
    assert data["talent_code"] == 1
    assert data["talent_source"] == "onboarding"
    db.close()


def test_returning_rejects_unknown_talent():
    init_db()
    db = get_session_factory()()
    user = ChildUser(parent_phone="13800001002", nickname="ret_bad")
    db.add(user)
    db.commit()
    db.refresh(user)

    with pytest.raises(OnboardingError, match="老学员必须选择五者天赋之一"):
        update_profile(
            db,
            user.id,
            profile_json={
                "onboarding": {
                    "student_type": "returning",
                    "talent_unknown": True,
                },
            },
        )
    db.close()


def test_returning_full_payload_persists_global_and_prior_data():
    init_db()
    db = get_session_factory()()
    user = ChildUser(parent_phone="13800001003", nickname="ret_full")
    db.add(user)
    db.commit()
    db.refresh(user)

    update_profile(
        db,
        user.id,
        profile_json={
            "onboarding": {
                "student_type": "returning",
                "completed_at": "2026-06-29T10:00:00.000Z",
                "self_reported_talent": "学者",
                "self_reported_talent_code": 1,
                "talent_unknown": False,
                "first_training_date": "2025年3月",
                "total_training_sessions": "120",
                "prior_abilities": ["超脑阅读", "影像追忆", "无效项目"],
                "prior_training_data": {
                    "超脑阅读": {
                        "firstDate": "2025年3月",
                        "totalCount": "30",
                        "lastTime": "20",
                        "lastResult": "85",
                        "note": "中途停过两个月",
                    },
                },
            },
        },
    )
    db.refresh(user)
    ob = user.profile_json["onboarding"]
    assert ob["first_training_date"] == "2025年3月"
    assert ob["total_training_sessions"] == 120
    assert ob["prior_abilities"] == ["超脑阅读", "影像追忆"]
    assert ob["prior_training_data"]["超脑阅读"]["totalCount"] == "30"
    assert "无效项目" not in ob["prior_training_data"]
    db.close()


def test_step3_then_step100_merge_without_losing_talent():
    init_db()
    db = get_session_factory()()
    user = ChildUser(parent_phone="13800001004", nickname="ret_merge")
    db.add(user)
    db.commit()
    db.refresh(user)

    update_profile(
        db,
        user.id,
        profile_json={
            "onboarding": {
                "student_type": "returning",
                "self_reported_talent": "思者",
                "self_reported_talent_code": 2,
                "talent_unknown": False,
            },
        },
    )
    update_profile(
        db,
        user.id,
        profile_json={
            "onboarding": {
                "completed_at": "2026-06-29T12:00:00.000Z",
                "first_training_date": "2024年6月",
                "total_training_sessions": 80,
                "prior_abilities": ["扫描速记"],
                "prior_training_data": {
                    "扫描速记": {
                        "firstDate": "2024年6月",
                        "totalCount": "15",
                        "lastTime": "",
                        "lastResult": "",
                        "note": "",
                    },
                },
            },
        },
    )
    db.refresh(user)
    ob = user.profile_json["onboarding"]
    assert ob["self_reported_talent"] == "思者"
    assert ob["self_reported_talent_code"] == 2
    assert ob["prior_abilities"] == ["扫描速记"]
    assert ob["total_training_sessions"] == 80
    db.close()


def test_normalize_onboarding_name_only_resolves_code():
    ob = normalize_onboarding(
        {
            "student_type": "new",
            "self_reported_talent": "行者",
            "talent_unknown": False,
        }
    )
    assert ob["self_reported_talent_code"] == 3
