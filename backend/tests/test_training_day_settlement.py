"""
训练日 4:00 结算 — 输入 / 输出 / 红绿灯（TDD）

settle_training_day(db, child_user_id, plan_date) 幂等归档：
  - 打卡记录写入 train_date
  - 有打卡则方案 completed
  - 累计 training_days、应用 pending_main_line_to
  - 更新 training_day_anchor 至下一训练日
"""

from datetime import date, timedelta

import pytest

from app.db.models import ChildUser, TrainingPlan, TrainingRecord
from app.services.child_training_state import get_training_progress, save_training_progress
from app.services.training_day_settlement import settle_training_day


def _plan_with_checkin(db, uid: int, plan_date: date, *, main_line: str = "A") -> tuple[TrainingPlan, TrainingRecord]:
    child = db.get(ChildUser, uid)
    save_training_progress(
        db,
        child,
        {
            "main_line": main_line,
            "skills": {},
            "main_line_sessions": 0,
            "training_days": 0,
            "training_day_anchor": None,
            "pending_main_line_to": None,
        },
    )
    plan = TrainingPlan(
        child_user_id=uid,
        plan_date=plan_date,
        status="pending",
        content_index=0,
        planned_minutes=45,
    )
    db.add(plan)
    db.flush()
    rec = TrainingRecord(
        child_user_id=uid,
        plan_id=plan.id,
        train_date=None,
        ability_type="超脑阅读",
        content="1200字",
        files_json=[{"name": "超脑阅读", "time": 1, "wordCount": 1200}],
    )
    db.add(rec)
    db.commit()
    db.refresh(plan)
    db.refresh(rec)
    return plan, rec


class TestSettleTrainingDay:
    def test_settle_stamps_records_and_completes_plan(self, db_session, child_with_assessment):
        """
        INPUT:  2026-06-26 方案 pending + 1 条无 train_date 的打卡
        OUTPUT: settled=True, plan.status=completed, record.train_date=2026-06-26, records_stamped=1
        """
        uid = child_with_assessment
        plan_date = date(2026, 6, 26)
        plan, rec = _plan_with_checkin(db_session, uid, plan_date)

        out = settle_training_day(db_session, uid, plan_date)
        db_session.commit()
        db_session.refresh(plan)
        db_session.refresh(rec)

        assert out["settled"] is True
        assert out["already_settled"] is False
        assert out["plan_id"] == plan.id
        assert out["plan_status"] == "completed"
        assert out["records_stamped"] == 1
        assert plan.status == "completed"
        assert rec.train_date == plan_date

    def test_settle_is_idempotent_no_double_bump(self, db_session, child_with_assessment):
        """
        INPUT:  同一 plan_date 连续结算两次
        OUTPUT: 第二次 already_settled=True；training_days 不重复 +1
        """
        uid = child_with_assessment
        plan_date = date(2026, 6, 26)
        _plan_with_checkin(db_session, uid, plan_date)

        first = settle_training_day(db_session, uid, plan_date)
        db_session.commit()
        child = db_session.get(ChildUser, uid)
        days_after_first = get_training_progress(child)["training_days"]

        second = settle_training_day(db_session, uid, plan_date)
        db_session.commit()
        child = db_session.get(ChildUser, uid)
        days_after_second = get_training_progress(child)["training_days"]

        assert first["settled"] is True
        assert first["training_days_bumped"] is True
        assert second["already_settled"] is True
        assert second["settled"] is False
        assert days_after_second == days_after_first == 1

    def test_settle_applies_pending_main_line_advance(self, db_session, child_with_assessment):
        """
        INPUT:  main_line=A, pending_main_line_to=B，方案有打卡
        OUTPUT: main_line=B, pending 清空, pending_applied=True
        """
        uid = child_with_assessment
        plan_date = date(2026, 6, 26)
        child = db_session.get(ChildUser, uid)
        save_training_progress(
            db_session,
            child,
            {
                "main_line": "A",
                "skills": {},
                "main_line_sessions": 2,
                "training_days": 0,
                "pending_main_line_to": "B",
            },
        )
        plan = TrainingPlan(
            child_user_id=uid,
            plan_date=plan_date,
            status="pending",
            content_index=0,
        )
        db_session.add(plan)
        db_session.flush()
        db_session.add(
            TrainingRecord(
                child_user_id=uid,
                plan_id=plan.id,
                ability_type="超脑阅读",
                content="1200字",
            )
        )
        db_session.commit()

        out = settle_training_day(db_session, uid, plan_date)
        db_session.commit()
        state = get_training_progress(db_session.get(ChildUser, uid))

        assert out["pending_applied"] is True
        assert out["main_line"] == "B"
        assert state["main_line"] == "B"
        assert state["pending_main_line_to"] is None
        assert state["main_line_sessions"] == 0

    def test_settle_advances_training_day_anchor(self, db_session, child_with_assessment):
        """
        INPUT:  结算 2026-06-26
        OUTPUT: training_day_anchor=2026-06-27（下一训练日）
        """
        uid = child_with_assessment
        plan_date = date(2026, 6, 26)
        _plan_with_checkin(db_session, uid, plan_date)

        out = settle_training_day(db_session, uid, plan_date)
        db_session.commit()
        state = get_training_progress(db_session.get(ChildUser, uid))

        assert out["next_training_day"] == "2026-06-27"
        assert state["training_day_anchor"] == "2026-06-27"

    def test_settle_no_plan_marks_empty_day(self, db_session, child_with_assessment):
        """
        INPUT:  该日无方案
        OUTPUT: settled=True, plan_id=None, records_stamped=0, already_settled 第二次为 True
        """
        uid = child_with_assessment
        plan_date = date(2026, 6, 26)

        out = settle_training_day(db_session, uid, plan_date)
        db_session.commit()

        assert out["settled"] is True
        assert out["plan_id"] is None
        assert out["records_stamped"] == 0
        assert out["training_days_bumped"] is False

        again = settle_training_day(db_session, uid, plan_date)
        assert again["already_settled"] is True

    def test_settle_plan_without_checkin_stays_pending(self, db_session, child_with_assessment):
        """
        INPUT:  有方案、无打卡
        OUTPUT: plan.status 仍为 pending，不累计 training_days
        """
        uid = child_with_assessment
        plan_date = date(2026, 6, 26)
        plan = TrainingPlan(
            child_user_id=uid,
            plan_date=plan_date,
            status="pending",
            content_index=0,
        )
        db_session.add(plan)
        db_session.commit()

        out = settle_training_day(db_session, uid, plan_date)
        db_session.commit()
        db_session.refresh(plan)

        assert out["plan_status"] == "pending"
        assert out["training_days_bumped"] is False
        assert plan.status == "pending"

    def test_history_excludes_active_today_after_settle(self, db_session, child_with_assessment):
        """
        INPUT:  结算昨日方案后，用 exclude_today 查历史
        OUTPUT: 昨日打卡出现在历史中
        """
        from app.services.dev_clock import set_time_override
        from app.services.training_day import plan_new_day_at
        from app.services.training_service import get_checkin_history

        uid = child_with_assessment
        plan_date = date(2026, 6, 26)
        _plan_with_checkin(db_session, uid, plan_date)
        settle_training_day(db_session, uid, plan_date)

        new_moment = plan_new_day_at(plan_date)
        set_time_override(db_session, uid, new_moment)
        db_session.commit()

        items = get_checkin_history(db_session, uid, limit=10, exclude_today=True)
        assert len(items) >= 1
        assert items[0]["ability_type"] == "超脑阅读"


class TestSettleDueTrainingDay:
    def test_settle_due_only_in_transition_window(self, db_session, child_with_assessment):
        """
        INPUT:  4:02 在空窗内 + 昨日方案有打卡；对比 10:00 非空窗
        OUTPUT: 空窗内返回结算结果；非空窗返回 None
        """
        from datetime import datetime, timezone

        from app.services.dev_clock import set_time_override
        from app.services.training_day import TZ
        from app.services.training_day_settlement import settle_due_training_day

        uid = child_with_assessment
        plan_date = date(2026, 6, 26)
        _plan_with_checkin(db_session, uid, plan_date)

        in_window = datetime(2026, 6, 27, 4, 2, tzinfo=TZ)
        set_time_override(db_session, uid, in_window)
        db_session.commit()

        due = settle_due_training_day(db_session, uid)
        assert due is not None
        assert due["settled"] is True
        assert due["plan_date"] == "2026-06-26"

        outside = datetime(2026, 6, 27, 10, 0, tzinfo=TZ)
        set_time_override(db_session, uid, outside)
        db_session.commit()
        assert settle_due_training_day(db_session, uid) is None
