# -*- coding: utf-8 -*-
"""老学员 onboarding 数据落地 — build_state_from_onboarding / update_profile 联动"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("JNAO_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.db.models import ChildUser
from app.services.child_training_state import (
    REQUIRED_SKILLS,
    build_state_from_onboarding,
    get_training_progress,
    overall_tier,
)
from app.services.user_service import update_profile


def _make_returning_child(db, *, grade: str = "一年级") -> ChildUser:
    user = ChildUser(
        parent_phone="13800002001",
        nickname="老学员童",
        profile_json={"grade": grade, "talent_code": 1},
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestBuildStateFromOnboarding:
    """单元：根据 prior_training_data 初始化 training_progress"""

    def test_passing_skill_high_total_count_tier2_pass3(self, db_session):
        child = _make_returning_child(db_session)
        state = build_state_from_onboarding(
            db_session,
            child,
            talent_code=1,
            prior_abilities=["超脑阅读"],
            prior_training_data={
                "超脑阅读": {
                    "wordCount": "900",
                    "time": "2",
                    "totalCount": "5",
                },
            },
        )
        assert state["skills"]["超脑阅读"]["tier"] == 2
        assert state["skills"]["超脑阅读"]["consecutive_pass"] == 3

    def test_passing_skill_low_total_count_tier2_pass1(self, db_session):
        child = _make_returning_child(db_session)
        state = build_state_from_onboarding(
            db_session,
            child,
            talent_code=1,
            prior_abilities=["超脑阅读"],
            prior_training_data={
                "超脑阅读": {
                    "wordCount": "900",
                    "time": "2",
                    "totalCount": "1",
                },
            },
        )
        assert state["skills"]["超脑阅读"]["tier"] == 2
        assert state["skills"]["超脑阅读"]["consecutive_pass"] == 1

    def test_failing_skill_stays_tier1(self, db_session):
        child = _make_returning_child(db_session)
        state = build_state_from_onboarding(
            db_session,
            child,
            talent_code=1,
            prior_abilities=["超脑阅读"],
            prior_training_data={
                "超脑阅读": {
                    "wordCount": "100",
                    "time": "10",
                    "totalCount": "20",
                },
            },
        )
        assert state["skills"]["超脑阅读"]["tier"] == 1
        assert state["skills"]["超脑阅读"]["consecutive_pass"] == 0

    def test_skip_jisuxuexi(self, db_session):
        child = _make_returning_child(db_session)
        state = build_state_from_onboarding(
            db_session,
            child,
            talent_code=1,
            prior_abilities=["极速学习"],
            prior_training_data={
                "极速学习": {
                    "wordCount": "1",
                    "time": "1",
                    "totalCount": "10",
                },
            },
        )
        assert state["skills"]["极速学习"]["tier"] == 1

    def test_overall_tier_reflects_initialized_skills(self, db_session):
        child = _make_returning_child(db_session)
        state = build_state_from_onboarding(
            db_session,
            child,
            talent_code=1,
            prior_abilities=["超脑阅读", "影像追忆"],
            prior_training_data={
                "超脑阅读": {"wordCount": "900", "time": "2", "totalCount": "3"},
                "影像追忆": {"wordCount": "2000", "accuracy_pct": 80, "time": "5", "totalCount": "1"},
            },
        )
        # 2 skills tier2 + 3 skills tier1 → min = 1
        assert overall_tier(state) == 1
        assert state["skills"]["影像追忆"]["tier"] == 2

    def test_persists_to_profile_json(self, db_session):
        child = _make_returning_child(db_session)
        build_state_from_onboarding(
            db_session,
            child,
            talent_code=1,
            prior_abilities=["超脑阅读"],
            prior_training_data={
                "超脑阅读": {"wordCount": "900", "time": "2", "totalCount": "3"},
            },
        )
        db_session.refresh(child)
        saved = get_training_progress(child)
        assert saved["skills"]["超脑阅读"]["tier"] == 2


class TestReturningProgressViaUpdateProfile:
    """集成：onboarding completed_at 触发 _try_init_returning_progress"""

    def test_completed_onboarding_initializes_progress_once(self, db_session):
        user = ChildUser(parent_phone="13800002002", nickname="ret_init")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        update_profile(
            db_session,
            user.id,
            profile_json={
                "grade": "一年级",
                "onboarding": {
                    "student_type": "returning",
                    "completed_at": "2026-07-01T10:00:00.000Z",
                    "self_reported_talent": "学者",
                    "self_reported_talent_code": 1,
                    "talent_unknown": False,
                    "prior_abilities": ["超脑阅读"],
                    "prior_training_data": {
                        "超脑阅读": {
                            "wordCount": "900",
                            "time": "2",
                            "totalCount": "4",
                        },
                    },
                },
            },
        )
        db_session.refresh(user)
        assert user.profile_json.get("talent_code") == 1
        progress = get_training_progress(user)
        assert progress["skills"]["超脑阅读"]["tier"] == 2

        # 再次更新不应重复初始化（已有 tier>1）
        update_profile(
            db_session,
            user.id,
            profile_json={
                "onboarding": {
                    "prior_training_data": {
                        "超脑阅读": {
                            "wordCount": "100",
                            "time": "10",
                            "totalCount": "1",
                        },
                    },
                },
            },
        )
        db_session.refresh(user)
        progress2 = get_training_progress(user)
        assert progress2["skills"]["超脑阅读"]["tier"] == 2
        assert progress2["skills"]["超脑阅读"]["consecutive_pass"] == 3

    def test_new_student_does_not_init_progress(self, db_session):
        user = ChildUser(parent_phone="13800002003", nickname="new_kid")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        update_profile(
            db_session,
            user.id,
            profile_json={
                "onboarding": {
                    "student_type": "new",
                    "completed_at": "2026-07-01T10:00:00.000Z",
                },
            },
        )
        db_session.refresh(user)
        progress = get_training_progress(user)
        for sk in REQUIRED_SKILLS:
            assert progress["skills"][sk]["tier"] == 1
