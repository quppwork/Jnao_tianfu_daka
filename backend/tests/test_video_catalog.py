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
    result = get_talent_training_video(1)
    assert result.get("source") == "oss_content"
    assert result.get("url")
