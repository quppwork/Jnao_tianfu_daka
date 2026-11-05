# -*- coding: utf-8 -*-
"""Part 轮换范围 + 新学员转老学员（2026-07-21 高风险 #1/#2）"""

from datetime import date

import pytest
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import ChildUser, TrainingItem, TrainingPlan, TrainingRecord
from app.services.child_training_state import (
    REQUIRED_SKILLS,
    get_training_progress,
    rotate_part_after_checkin,
    save_training_progress,
)
from app.services.training_service import (
    _auto_promote_to_returning,
    _skills_for_part_rotation,
    _try_rotate_part_after_checkin,
)


def _make_child(db, *, student_type="new", completed_at=None) -> ChildUser:
    onboarding = {"student_type": student_type}
    if completed_at is not None:
        onboarding["completed_at"] = completed_at
    user = ChildUser(
        parent_phone="13900007021",
        nickname="轮换测试",
        profile_json={"onboarding": onboarding, "talent_code": 1},
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # 初始化 training_progress
    state = get_training_progress(user)
    save_training_progress(db, user, state)
    flag_modified(user, "profile_json")
    db.commit()
    db.refresh(user)
    return user


class TestSkillsForPartRotation:
    def test_from_cards_only_required(self):
        cards = [
            {"name": "影像追忆", "time": 10},
            {"name": "多元感知", "time": 5},
            {"name": "影像追忆", "time": 8},
        ]
        assert _skills_for_part_rotation(cards, None) == ["影像追忆"]

    def test_fallback_to_item_instructions(self):
        item = TrainingItem(
            plan_id=0,
            sort_order=1,
            title="某课",
            instructions='{"skill": "扫描速记", "item_type": "audio"}',
            checkin_status="pending",
        )
        assert _skills_for_part_rotation(None, item) == ["扫描速记"]


class TestPartRotationScope:
    def test_only_checked_skill_increments(self, db_session):
        child = _make_child(db_session)
        _try_rotate_part_after_checkin(
            db_session,
            child,
            talent_code=1,
            cards=[{"name": "影像追忆", "time": 10}],
            target_item=None,
        )
        db_session.commit()
        db_session.refresh(child)

        state = get_training_progress(child)
        assert state["skills"]["影像追忆"]["part_listen_count"] == 1
        assert state["skills"]["影像追忆"]["part_first_listen_at"]
        for sk in REQUIRED_SKILLS:
            if sk == "影像追忆":
                continue
            assert state["skills"][sk]["part_listen_count"] == 0

    def test_new_user_rotates_after_five_on_same_skill(self, db_session):
        child = _make_child(db_session, student_type="new")
        before = get_training_progress(child)
        part_before = before["skills"]["超脑阅读"]["oss_part"]

        for _ in range(5):
            _try_rotate_part_after_checkin(
                db_session,
                child,
                talent_code=1,
                cards=[{"name": "超脑阅读"}],
            )
            db_session.commit()
            db_session.refresh(child)

        state = get_training_progress(child)
        # 超脑阅读无 OSS stage 时也可能回到 part=1；计数应已归零（轮换发生）
        assert state["skills"]["超脑阅读"]["part_listen_count"] == 0
        # 其它技能未动
        assert state["skills"]["影像追忆"]["part_listen_count"] == 0


class TestPartFirstListenBackfill:
    """#13：老学员有 count 无 first_at → 补写后走 7 天内阈值 20"""

    def test_dirty_returning_backfills_and_uses_20(self):
        from app.services.child_training_state import (
            PART_ROTATION_RETURNING_7D,
            _default_state,
            _part_rotation_threshold,
        )

        state = _default_state()
        sd = state["skills"]["影像追忆"]
        sd["part_listen_count"] = 10
        sd["part_first_listen_at"] = None
        # 模拟打卡路径：缺时间戳则补写
        rotated = rotate_part_after_checkin(state, "影像追忆", student_type="returning")
        assert sd["part_first_listen_at"]
        assert sd["part_listen_count"] == 11
        assert not rotated  # 11 < 20
        assert _part_rotation_threshold("returning", sd) == PART_ROTATION_RETURNING_7D


class TestAutoPromoteReturning:
    def _seed_records(self, db, child_id: int, n: int) -> None:
        plan = TrainingPlan(
            child_user_id=child_id,
            plan_date=date(2026, 7, 1),
            level="视觉",
            report_text="",
            status="completed",
            content_index=0,
        )
        db.add(plan)
        db.flush()
        for i in range(n):
            db.add(
                TrainingRecord(
                    child_user_id=child_id,
                    plan_id=plan.id,
                    train_date=date(2026, 7, 1),
                    ability_type="audio",
                )
            )
        db.commit()

    def test_promotes_with_completed_at(self, db_session):
        child = _make_child(
            db_session, student_type="new", completed_at="2026-06-01T00:00:00+08:00"
        )
        self._seed_records(db_session, child.id, 30)
        _auto_promote_to_returning(db_session, child.id)
        db_session.refresh(child)
        ob = child.profile_json["onboarding"]
        assert ob["student_type"] == "returning"
        assert ob.get("promoted_to_returning_at")

    def test_not_yet_at_30(self, db_session):
        child = _make_child(
            db_session, student_type="new", completed_at="2026-06-01T00:00:00+08:00"
        )
        self._seed_records(db_session, child.id, 29)
        _auto_promote_to_returning(db_session, child.id)
        db_session.refresh(child)
        assert child.profile_json["onboarding"]["student_type"] == "new"

    def test_already_returning_unchanged(self, db_session):
        child = _make_child(db_session, student_type="returning", completed_at="x")
        self._seed_records(db_session, child.id, 50)
        _auto_promote_to_returning(db_session, child.id)
        db_session.refresh(child)
        assert child.profile_json["onboarding"]["student_type"] == "returning"
        assert "promoted_to_returning_at" not in child.profile_json["onboarding"]
