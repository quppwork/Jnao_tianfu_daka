"""OSS 训练视频目录导入"""

from sqlalchemy import select

from app.db.models import ContentItem
from app.services.catalog_import import import_video_catalog
from app.services.content_meta import parse_item_meta
from app.services.training_catalog_sync import ensure_supplementary_catalogs
from app.services.training_schedule_service import _attach_videos_to_items
from app.services.video_push_service import get_talent_training_video


def test_import_video_catalog(db_session):
    n = import_video_catalog(db_session)
    assert n >= 5
    videos = db_session.scalars(
        select(ContentItem).where(ContentItem.content_type == "video")
    ).all()
    skills = {parse_item_meta(v).get("skill") for v in videos}
    assert "开口窍" in skills
    assert "极速运算" in skills
    assert "五者天赋" in skills


def test_ensure_supplementary_includes_videos(db_session):
    before = db_session.scalar(
        select(ContentItem).where(ContentItem.content_type == "video")
    )
    added = ensure_supplementary_catalogs(db_session)
    assert added >= 0
    count = len(
        db_session.scalars(
            select(ContentItem).where(ContentItem.content_type == "video")
        ).all()
    )
    assert count >= 5


def test_attach_jisu_video_to_plan(db_session, child_with_assessment):
    from app.db.models import TrainingItem, TrainingPlan
    from app.services.training_day import get_training_day

    import_video_catalog(db_session)
    uid = child_with_assessment
    plan = TrainingPlan(
        child_user_id=uid,
        plan_date=get_training_day(),
        content_index=1,
        status="pending",
    )
    db_session.add(plan)
    db_session.flush()
    db_session.add(
        TrainingItem(
            plan_id=plan.id,
            sort_order=1,
            ability_type="audio",
            title="极速运算训练",
            duration_min=10,
            instructions='{"skill":"极速运算","item_type":"required"}',
            checkin_status="pending",
        )
    )
    db_session.flush()
    _attach_videos_to_items(db_session, plan)
    item = plan.items[0]
    assert item.video_url
    assert "极速运算" in item.video_url or "shipin" in item.video_url


def test_talent_video_from_oss(db_session):
    import_video_catalog(db_session)
    result = get_talent_training_video(1, db=db_session)
    assert result.get("source") == "oss_content"
    assert result.get("url") == "/api/training/video/talent/stream"


def test_attach_video_on_elective_append(db_session, child_with_assessment):
    from app.db.models import TrainingItem, TrainingPlan
    from app.services.training_day import get_training_day
    from app.services.training_service import append_elective_item

    import_video_catalog(db_session)
    uid = child_with_assessment
    plan = TrainingPlan(
        child_user_id=uid,
        plan_date=get_training_day(),
        content_index=1,
        planned_minutes=45,
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
            duration_min=10,
            audio_url="https://example.com/a.mp3",
            instructions='{"skill":"超脑阅读","item_type":"required"}',
            checkin_status="pending",
        )
    )
    db_session.commit()

    append_elective_item(db_session, uid, plan.id, "极速运算")
    db_session.refresh(plan)
    jisu = next(
        i for i in plan.items
        if '"skill": "极速运算"' in (i.instructions or "") or '"skill":"极速运算"' in (i.instructions or "")
    )
    assert jisu.video_url
    assert "shipin" in jisu.video_url or "极速运算" in jisu.video_url


def test_repair_plan_fills_missing_video(db_session, child_with_assessment):
    from app.db.models import TrainingItem, TrainingPlan
    from app.services.training_day import get_training_day
    from app.services.training_catalog_sync import repair_plan_media_items

    import_video_catalog(db_session)
    uid = child_with_assessment
    plan = TrainingPlan(
        child_user_id=uid,
        plan_date=get_training_day(),
        content_index=1,
        planned_minutes=45,
        status="pending",
    )
    db_session.add(plan)
    db_session.flush()
    db_session.add(
        TrainingItem(
            plan_id=plan.id,
            sort_order=1,
            ability_type="audio",
            title="极速运算训练",
            duration_min=10,
            audio_url="https://example.com/a.mp3",
            instructions='{"skill":"极速运算","item_type":"required"}',
            checkin_status="pending",
        )
    )
    db_session.commit()

    n = repair_plan_media_items(db_session, plan, talent_code=1)
    assert n >= 1
    assert plan.items[0].video_url


def test_attach_clears_video_for_skill_without_catalog(db_session, child_with_assessment):
    from app.db.models import TrainingItem, TrainingPlan
    from app.services.training_day import get_training_day
    from app.services.training_video_attach import attach_videos_to_plan_items

    import_video_catalog(db_session)
    plan = TrainingPlan(
        child_user_id=child_with_assessment,
        plan_date=get_training_day(),
        content_index=1,
        status="pending",
    )
    db_session.add(plan)
    db_session.flush()
    db_session.add(
        TrainingItem(
            plan_id=plan.id,
            sort_order=1,
            ability_type="audio",
            title="思者影像追忆1阶段1",
            duration_min=10,
            audio_url="https://example.com/a.mp3",
            video_url="https://jnao-talent-ai.oss-cn-beijing.aliyuncs.com/shipin/stale.mp4",
            instructions='{"skill":"影像追忆","item_type":"required"}',
            checkin_status="pending",
        )
    )
    db_session.flush()
    n = attach_videos_to_plan_items(db_session, plan, only_missing=False)
    assert n >= 1
    assert plan.items[0].video_url is None


def test_attach_clears_video_for_skill_without_catalog(db_session, child_with_assessment):
    from app.db.models import TrainingItem, TrainingPlan
    from app.services.training_day import get_training_day
    from app.services.training_video_attach import attach_videos_to_plan_items

    import_video_catalog(db_session)
    plan = TrainingPlan(
        child_user_id=child_with_assessment,
        plan_date=get_training_day(),
        content_index=1,
        status="pending",
    )
    db_session.add(plan)
    db_session.flush()
    db_session.add(
        TrainingItem(
            plan_id=plan.id,
            sort_order=1,
            ability_type="audio",
            title="思者影像追忆1阶段1",
            duration_min=10,
            audio_url="https://example.com/a.mp3",
            video_url="https://jnao-talent-ai.oss-cn-beijing.aliyuncs.com/shipin/stale.mp4",
            instructions='{"skill":"影像追忆","item_type":"required"}',
            checkin_status="pending",
        )
    )
    db_session.flush()
    n = attach_videos_to_plan_items(db_session, plan, only_missing=False)
    assert n >= 1
    assert plan.items[0].video_url is None
