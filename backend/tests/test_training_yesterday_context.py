# -*- coding: utf-8 -*-
"""昨日训练上下文 — result/note 回流 AI"""

from datetime import timedelta

from app.db.models import TrainingPlan, TrainingRecord
from app.services.training_day import get_training_day
from app.services.training_service import get_or_create_today_plan, get_yesterday_training_context


def test_yesterday_context_includes_result_and_note(db_session, child_with_assessment):
    yesterday = get_training_day() - timedelta(days=1)
    plan_y = get_or_create_today_plan(db_session, child_with_assessment, yesterday)
    plan = db_session.get(TrainingPlan, plan_y["plan_id"])
    plan.status = "completed"
    item = plan.items[0]
    item.checkin_status = "done"
    db_session.add(
        TrainingRecord(
            child_user_id=child_with_assessment,
            plan_id=plan.id,
            item_id=item.id,
            ability_type="超脑阅读",
            attitude_pct=80,
            content="完成训练",
            result="速度有提升",
            note="晚上有点困",
            files_json=[
                {
                    "name": "超脑阅读",
                    "time": "15",
                    "result": "比昨天顺",
                    "note": "字词还需巩固",
                },
            ],
        )
    )
    db_session.commit()

    ctx = get_yesterday_training_context(db_session, child_with_assessment)
    assert ctx
    assert "速度有提升" in ctx
    assert "晚上有点困" in ctx
    assert "比昨天顺" in ctx
    assert "字词还需巩固" in ctx
