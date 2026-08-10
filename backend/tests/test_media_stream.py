"""训练/OSS 媒体流代理"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def test_training_item_stream_returns_audio(client: TestClient, db_session, child_with_assessment):
    from app.db.models import TrainingItem, TrainingPlan
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
    item = TrainingItem(
        plan_id=plan.id,
        sort_order=1,
        ability_type="audio",
        title="测试音频",
        audio_url="https://jnao-talent-ai.oss-cn-beijing.aliyuncs.com/yinpin/test.mp3",
        duration_min=5,
        instructions='{"skill":"超脑阅读","item_type":"audio"}',
        checkin_status="pending",
    )
    db_session.add(item)
    db_session.commit()

    mock_result = MagicMock()
    mock_result.read.side_effect = [b"abc", b""]
    mock_result.headers = {"Content-Type": "audio/mpeg", "Content-Length": "3"}
    mock_result.close = MagicMock()

    with patch("app.services.oss_stream_service._bucket_client") as mock_bucket:
        mock_bucket.return_value.get_object.return_value = mock_result
        resp = client.get(
            f"/api/training/items/{item.id}/stream?media=audio&user_id={uid}",
        )
    assert resp.status_code == 200
    assert resp.content == b"abc"
    assert "audio" in resp.headers.get("content-type", "")


def test_item_to_dict_uses_stream_urls(db_session):
    from app.db.models import TrainingItem, TrainingPlan
    from app.services.training_day import get_training_day
    from app.services.training_service import _item_to_dict

    plan = TrainingPlan(
        child_user_id=1,
        plan_date=get_training_day(),
        content_index=0,
        status="pending",
    )
    db_session.add(plan)
    db_session.flush()
    item = TrainingItem(
        plan_id=plan.id,
        sort_order=1,
        ability_type="audio",
        title="音频",
        audio_url="https://jnao-talent-ai.oss-cn-beijing.aliyuncs.com/yinpin/a.mp3",
        duration_min=5,
        instructions='{"skill":"超脑阅读"}',
        checkin_status="pending",
    )
    db_session.add(item)
    db_session.flush()

    data = _item_to_dict(item)
    assert data["audio_url"] == f"/api/training/items/{item.id}/stream?media=audio"
    assert "oss-cn-beijing" not in (data["audio_url"] or "")


def test_training_item_stream_accepts_media_token(client: TestClient, db_session, child_with_assessment):
    from app.core.media_stream_token import make_media_stream_token
    from app.db.models import TrainingItem, TrainingPlan
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
    item = TrainingItem(
        plan_id=plan.id,
        sort_order=1,
        ability_type="video",
        title="超脑阅读",
        video_url="https://jnao-talent-ai.oss-cn-beijing.aliyuncs.com/shipin/test.mp4",
        duration_min=5,
        instructions='{"skill":"超脑阅读","item_type":"video"}',
        checkin_status="pending",
    )
    db_session.add(item)
    db_session.commit()

    mt = make_media_stream_token(item.id, uid, "video")
    mock_result = MagicMock()
    mock_result.read.side_effect = [b"vid", b""]
    mock_result.headers = {"Content-Type": "video/mp4", "Content-Length": "3"}
    mock_result.close = MagicMock()

    with patch("app.services.oss_stream_service._bucket_client") as mock_bucket:
        mock_bucket.return_value.get_object.return_value = mock_result
        resp = client.get(
            f"/api/training/items/{item.id}/stream?media=video&user_id={uid}&mt={mt}",
        )
    assert resp.status_code == 200
    assert resp.content == b"vid"
