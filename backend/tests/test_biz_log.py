"""biz_log 行为日志格式单测"""

from app.core.biz_log import (
    bind_user,
    biz_event,
    get_request_id,
    reset_context,
    set_request_id,
    should_log_http,
)


def test_biz_event_includes_uid_and_rid(caplog):
    reset_context()
    set_request_id("abc123def456")
    bind_user(42, role="student")
    with caplog.at_level("INFO", logger="biz"):
        biz_event("training.checkin", result="ok", ms=12.3, plan_id=9)
    assert any("biz action=training.checkin" in r.message for r in caplog.records)
    msg = next(r.message for r in caplog.records if "training.checkin" in r.message)
    assert "uid=42" in msg
    assert "role=student" in msg
    assert "rid=abc123def456" in msg
    assert "plan_id=9" in msg
    assert get_request_id() == "abc123def456"


def test_should_log_http_filters_noise():
    assert should_log_http("/api/training/checkin", 200) is True
    assert should_log_http("/api/ping", 200) is False
    assert should_log_http("/api/ping", 500) is True
    assert should_log_http("/api/training/items/1/stream", 200) is False
