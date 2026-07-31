# -*- coding: utf-8 -*-
"""QA 对话限流：短窗 QPS + 日限额（与 Guide 分桶）"""

import pytest
from fastapi import HTTPException

from app.core.rate_limit import (
    check_guide_chat_limits,
    check_qa_chat_limits,
    reset_rate_limit_buckets,
)


@pytest.fixture(autouse=True)
def _clear_buckets():
    reset_rate_limit_buckets()
    yield
    reset_rate_limit_buckets()


def test_qa_chat_qps_window(monkeypatch):
    monkeypatch.setenv("QA_CHAT_RATE_LIMIT", "1")
    monkeypatch.setenv("QA_CHAT_QPS_MAX", "3")
    monkeypatch.setenv("QA_CHAT_QPS_WINDOW_SEC", "60")
    monkeypatch.setenv("QA_CHAT_DAY_MAX", "1000")
    uid = 91001
    for _ in range(3):
        check_qa_chat_limits(uid)
    with pytest.raises(HTTPException) as exc:
        check_qa_chat_limits(uid)
    assert exc.value.status_code == 429
    assert "太快" in str(exc.value.detail)


def test_qa_chat_day_cap(monkeypatch):
    monkeypatch.setenv("QA_CHAT_RATE_LIMIT", "1")
    monkeypatch.setenv("QA_CHAT_QPS_MAX", "1000")
    monkeypatch.setenv("QA_CHAT_QPS_WINDOW_SEC", "60")
    monkeypatch.setenv("QA_CHAT_DAY_MAX", "2")
    uid = 91002
    check_qa_chat_limits(uid)
    check_qa_chat_limits(uid)
    with pytest.raises(HTTPException) as exc:
        check_qa_chat_limits(uid)
    assert exc.value.status_code == 429
    assert "今天" in str(exc.value.detail)


def test_qa_chat_rate_limit_disabled(monkeypatch):
    monkeypatch.setenv("QA_CHAT_RATE_LIMIT", "0")
    monkeypatch.setenv("QA_CHAT_QPS_MAX", "1")
    for _ in range(5):
        check_qa_chat_limits(91003)


def test_qa_and_guide_buckets_independent(monkeypatch):
    monkeypatch.setenv("QA_CHAT_RATE_LIMIT", "1")
    monkeypatch.setenv("QA_CHAT_QPS_MAX", "1")
    monkeypatch.setenv("QA_CHAT_QPS_WINDOW_SEC", "60")
    monkeypatch.setenv("QA_CHAT_DAY_MAX", "1000")
    monkeypatch.setenv("GUIDE_CHAT_RATE_LIMIT", "1")
    monkeypatch.setenv("GUIDE_CHAT_QPS_MAX", "1")
    monkeypatch.setenv("GUIDE_CHAT_QPS_WINDOW_SEC", "60")
    monkeypatch.setenv("GUIDE_CHAT_DAY_MAX", "1000")
    uid = 91004
    check_qa_chat_limits(uid)
    check_guide_chat_limits(uid)  # 不同桶，不应因 QA 已用而 429
    with pytest.raises(HTTPException):
        check_qa_chat_limits(uid)


def test_qa_chat_api_returns_429(client, monkeypatch, registered_user):
    monkeypatch.setenv("QA_CHAT_RATE_LIMIT", "1")
    monkeypatch.setenv("QA_CHAT_QPS_MAX", "2")
    monkeypatch.setenv("QA_CHAT_QPS_WINDOW_SEC", "60")
    monkeypatch.setenv("QA_CHAT_DAY_MAX", "1000")
    uid = registered_user["child_user_id"]
    body = {"message": "你好老师", "subject": "数学"}
    url = f"/api/qa/chat?user_id={uid}"
    r1 = client.post(url, json=body)
    r2 = client.post(url, json=body)
    r3 = client.post(url, json=body)
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert r3.status_code == 429, r3.text
    assert "太快" in (r3.json().get("detail") or "")
