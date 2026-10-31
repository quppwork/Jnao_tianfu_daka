"""训练/OSS 媒体流代理"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def test_training_item_stream_returns_audio(client: TestClient, db_session, child_with_assessment, monkeypatch):
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

    monkeypatch.setenv("OSS_MEDIA_DIRECT_REDIRECT", "0")

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


def test_item_to_dict_uses_cdn_signed_url(db_session, monkeypatch):
    from app.db.models import TrainingItem, TrainingPlan
    from app.services.training_day import get_training_day
    from app.services.training_service import _item_to_dict

    monkeypatch.setenv("OSS_CDN_DOMAIN", "media.example.com")
    monkeypatch.setenv("OSS_ACCESS_KEY_ID", "test-id")
    monkeypatch.setenv("OSS_ACCESS_KEY_SECRET", "test-secret")

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
        ability_type="video",
        title="超脑阅读",
        video_url="https://jnao-talent-ai.oss-cn-beijing.aliyuncs.com/shipin/a.mp4",
        duration_min=5,
        instructions='{"skill":"超脑阅读","item_type":"video"}',
        checkin_status="pending",
    )
    db_session.add(item)
    db_session.flush()

    signed = "https://jnao-talent-ai.oss-cn-beijing.aliyuncs.com/shipin/a.mp4?sig=1"
    cdn = "https://media.example.com/shipin/a.mp4?sig=1"
    with patch("app.services.oss_client.sign_cdn_play_url", return_value=cdn), patch(
        "app.services.oss_client.use_cdn_for_media", return_value=True
    ):
        data = _item_to_dict(item, child_user_id=1)
    assert data["video_url"] == cdn
    assert "/api/training/items/" not in (data["video_url"] or "")


def test_training_item_stream_redirects_to_cdn(client: TestClient, db_session, child_with_assessment, monkeypatch):
    from app.db.models import TrainingItem, TrainingPlan
    from app.services.training_day import get_training_day

    monkeypatch.setenv("OSS_CDN_DOMAIN", "media.example.com")
    monkeypatch.setenv("OSS_ACCESS_KEY_ID", "test-id")
    monkeypatch.setenv("OSS_ACCESS_KEY_SECRET", "test-secret")

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

    cdn_url = "https://media.example.com/shipin/test.mp4?Expires=1&Signature=abc"
    with patch("app.services.media_redirect.sign_cdn_play_url", return_value=cdn_url), patch(
        "app.services.media_redirect.use_cdn_for_media", return_value=True
    ):
        resp = client.get(
            f"/api/training/items/{item.id}/stream?media=video&user_id={uid}",
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert resp.headers["location"] == cdn_url


def test_training_item_stream_redirects_to_oss(client: TestClient, db_session, child_with_assessment, monkeypatch):
    from app.db.models import TrainingItem, TrainingPlan
    from app.services.training_day import get_training_day

    monkeypatch.setenv("OSS_ACCESS_KEY_ID", "test-id")
    monkeypatch.setenv("OSS_ACCESS_KEY_SECRET", "test-secret")
    monkeypatch.setenv("OSS_MEDIA_DIRECT_REDIRECT", "1")
    monkeypatch.setenv("OSS_MEDIA_SAME_ORIGIN_CACHE", "0")

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

    oss_url = "https://jnao-talent-ai.oss-cn-beijing.aliyuncs.com/shipin/test.mp4?Expires=1&Signature=abc"
    with patch("app.services.media_redirect.sign_play_url", return_value=oss_url), patch(
        "app.services.media_redirect.use_cdn_for_media", return_value=False
    ):
        resp = client.get(
            f"/api/training/items/{item.id}/stream?media=video&user_id={uid}",
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert resp.headers["location"] == oss_url


def test_training_item_stream_same_origin_cache_redirect(client: TestClient, db_session, child_with_assessment, monkeypatch):
    from app.db.models import TrainingItem, TrainingPlan
    from app.services.training_day import get_training_day

    monkeypatch.setenv("OSS_ACCESS_KEY_ID", "test-id")
    monkeypatch.setenv("OSS_ACCESS_KEY_SECRET", "test-secret")
    monkeypatch.setenv("OSS_MEDIA_DIRECT_REDIRECT", "1")
    monkeypatch.setenv("OSS_MEDIA_SAME_ORIGIN_CACHE", "1")
    monkeypatch.setenv("SITE_DOMAIN", "https://jnaosoft.cn")

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

    oss_url = "https://jnao-talent-ai.oss-cn-beijing.aliyuncs.com/yinpin/test.mp3?Expires=9&Signature=xyz"
    with patch("app.services.media_redirect.sign_play_url", return_value=oss_url), patch(
        "app.services.media_redirect.use_cdn_for_media", return_value=False
    ):
        resp = client.get(
            f"/api/training/items/{item.id}/stream?media=audio&user_id={uid}",
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert resp.headers["location"] == (
        "https://jnaosoft.cn/api/media/oss/yinpin/test.mp3?Expires=9&Signature=xyz"
    )


def test_training_item_stream_auto_same_origin_when_site_domain(
    client: TestClient, db_session, child_with_assessment, monkeypatch
):
    from app.db.models import TrainingItem, TrainingPlan
    from app.services.training_day import get_training_day

    monkeypatch.setenv("OSS_ACCESS_KEY_ID", "test-id")
    monkeypatch.setenv("OSS_ACCESS_KEY_SECRET", "test-secret")
    monkeypatch.setenv("OSS_MEDIA_DIRECT_REDIRECT", "1")
    monkeypatch.delenv("OSS_MEDIA_SAME_ORIGIN_CACHE", raising=False)
    monkeypatch.setenv("SITE_DOMAIN", "https://jnaosoft.cn")

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

    oss_url = "https://jnao-talent-ai.oss-cn-beijing.aliyuncs.com/shipin/test.mp4?Expires=1&Signature=abc"
    with patch("app.services.media_redirect.sign_play_url", return_value=oss_url), patch(
        "app.services.media_redirect.use_cdn_for_media", return_value=False
    ):
        resp = client.get(
            f"/api/training/items/{item.id}/stream?media=video&user_id={uid}",
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert resp.headers["location"] == (
        "https://jnaosoft.cn/api/media/oss/shipin/test.mp4?Expires=1&Signature=abc"
    )


def test_training_item_stream_accepts_media_token(client: TestClient, db_session, child_with_assessment, monkeypatch):
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

    monkeypatch.setenv("OSS_MEDIA_DIRECT_REDIRECT", "0")

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
