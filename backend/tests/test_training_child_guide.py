import pytest
"""孩子训练指引与媒体修复"""

from app.services.training_child_guide import build_coach_text_for_plan, is_technical_schedule_note
from app.services.training_catalog_sync import ensure_supplementary_catalogs, repair_plan_media_items




def test_coach_text_not_technical(db_session, child_with_assessment):
    from app.db.models import TrainingPlan, TrainingItem
    from app.services.training_day import get_training_day

    uid = child_with_assessment
    plan = TrainingPlan(
        child_user_id=uid,
        plan_date=get_training_day(),
        content_index=0,
        status="pending",
    )
    db_session.add(plan)
    db_session.flush()
    db_session.add(
        TrainingItem(
            plan_id=plan.id,
            sort_order=1,
            ability_type="audio",
            title="超脑阅读",
            duration_min=9,
            instructions='{"block":"A","item_type":"audio","skill":"超脑阅读"}',
            checkin_status="pending",
        )
    )
    db_session.add(
        TrainingItem(
            plan_id=plan.id,
            sort_order=2,
            ability_type="perception",
            title="学者多元感知",
            duration_min=12,
            audio_url="https://example.com/p.mp3",
            instructions='{"block":"B","item_type":"perception","skill":"感知力"}',
            checkin_status="pending",
        )
    )
    db_session.flush()
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    plan = db_session.scalar(
        select(TrainingPlan)
        .options(selectinload(TrainingPlan.items))
        .where(TrainingPlan.id == plan.id)
    )
    text = build_coach_text_for_plan(plan)
    assert "训练块" not in text
    assert "超脑阅读" in text
    assert "多元感知" in text
    assert not is_technical_schedule_note(text)


def test_repair_perception_item(db_session, child_with_assessment):
    from app.db.models import TrainingPlan, TrainingItem
    from app.services.training_day import get_training_day

    ensure_supplementary_catalogs(db_session)
    uid = child_with_assessment
    plan = TrainingPlan(
        child_user_id=uid,
        plan_date=get_training_day(),
        content_index=0,
        status="pending",
    )
    db_session.add(plan)
    db_session.flush()
    item = TrainingItem(
        plan_id=plan.id,
        sort_order=2,
        ability_type="placeholder",
        title="多元感知（待同步）",
        instructions='{"block":"A","item_type":"perception"}',
        checkin_status="pending",
    )
    db_session.add(item)
    db_session.flush()
    n = repair_plan_media_items(db_session, plan, 1)
    assert n == 1
    assert item.audio_url
    assert item.ability_type == "perception"
    assert "待同步" not in (item.title or "")
