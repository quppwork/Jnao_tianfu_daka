# -*- coding: utf-8 -*-
"""Guide 对话限流 R13：短窗 QPS + 日限额"""

import pytest
from fastapi import HTTPException

from app.core.rate_limit import (
    check_guide_chat_limits,
    check_rate_limit,
    reset_rate_limit_buckets,
)


@pytest.fixture(autouse=True)
def _clear_buckets():
    reset_rate_limit_buckets()
    yield
    reset_rate_limit_buckets()


def test_check_rate_limit_custom_detail():
    check_rate_limit("t:a", max_calls=1, window_sec=60, detail="自定义")
    with pytest.raises(HTTPException) as exc:
        check_rate_limit("t:a", max_calls=1, window_sec=60, detail="自定义")
    assert exc.value.status_code == 429
    assert exc.value.detail == "自定义"


def test_guide_chat_qps_window(monkeypatch):
    monkeypatch.setenv("GUIDE_CHAT_RATE_LIMIT", "1")
    monkeypatch.setenv("GUIDE_CHAT_QPS_MAX", "3")
    monkeypatch.setenv("GUIDE_CHAT_QPS_WINDOW_SEC", "60")
    monkeypatch.setenv("GUIDE_CHAT_DAY_MAX", "1000")
    uid = 90001
    for _ in range(3):
        check_guide_chat_limits(uid)
    with pytest.raises(HTTPException) as exc:
        check_guide_chat_limits(uid)
    assert exc.value.status_code == 429
    assert "太快" in str(exc.value.detail)


def test_guide_chat_day_cap(monkeypatch):
    monkeypatch.setenv("GUIDE_CHAT_RATE_LIMIT", "1")
    monkeypatch.setenv("GUIDE_CHAT_QPS_MAX", "1000")
    monkeypatch.setenv("GUIDE_CHAT_QPS_WINDOW_SEC", "60")
    monkeypatch.setenv("GUIDE_CHAT_DAY_MAX", "2")
    uid = 90002
    check_guide_chat_limits(uid)
    check_guide_chat_limits(uid)
    with pytest.raises(HTTPException) as exc:
        check_guide_chat_limits(uid)
    assert exc.value.status_code == 429
    assert "今天" in str(exc.value.detail)


def test_guide_chat_rate_limit_disabled(monkeypatch):
    monkeypatch.setenv("GUIDE_CHAT_RATE_LIMIT", "0")
    monkeypatch.setenv("GUIDE_CHAT_QPS_MAX", "1")
    for _ in range(5):
        check_guide_chat_limits(90003)


def test_guide_chat_api_returns_429(client, monkeypatch, registered_user):
    """HTTP 层：连续超短窗应 429（不依赖豆包真实密钥）。"""
    monkeypatch.setenv("GUIDE_CHAT_RATE_LIMIT", "1")
    monkeypatch.setenv("GUIDE_CHAT_QPS_MAX", "2")
    monkeypatch.setenv("GUIDE_CHAT_QPS_WINDOW_SEC", "60")
    monkeypatch.setenv("GUIDE_CHAT_DAY_MAX", "1000")
    uid = registered_user["child_user_id"]
    body = {"message": "你好老师"}
    url = f"/api/guide/chat?user_id={uid}"
    r1 = client.post(url, json=body)
    r2 = client.post(url, json=body)
    r3 = client.post(url, json=body)
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert r3.status_code == 429, r3.text
    assert "太快" in (r3.json().get("detail") or "")
