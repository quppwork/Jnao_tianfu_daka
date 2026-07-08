"""低优先级安全加固 — B15/B19 等"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.services import auth_service
from app.services.wechat_auth_service import (
    BIND_SMS_MAX_PER_TICKET,
    assert_bind_ticket_sms_allowed,
    create_bind_ticket,
)


class TestLoginNameLockout:
    def test_student_login_lockout_after_failures(self, client: TestClient, db_session):
        auth_service.register_child(
            db_session,
            parent_phone="13900007701",
            nickname="家长锁",
            role=auth_service.ROLE_PARENT,
            child_quota=5,
        )
        auth_service.register_child(
            db_session,
            parent_phone="13900007701",
            nickname="锁定童",
            login_name="lock_kid",
            password="111111",
            role=auth_service.ROLE_STUDENT,
        )
        for _ in range(10):
            client.post(
                "/api/auth/login",
                json={"login_name": "lock_kid", "password": "wrong1"},
            )
        res = client.post(
            "/api/auth/login",
            json={"login_name": "lock_kid", "password": "111111"},
        )
        assert res.status_code == 429


class TestBindTicketSmsLimit:
    def test_bind_ticket_sms_count_and_phone_lock(self):
        ticket = create_bind_ticket(openid="o_bind_limit", unionid=None, wx_member_id=None)
        phone = "13900007711"
        for _ in range(BIND_SMS_MAX_PER_TICKET):
            assert_bind_ticket_sms_allowed(ticket, phone)
        with pytest.raises(HTTPException) as exc:
            assert_bind_ticket_sms_allowed(ticket, phone)
        assert exc.value.status_code == 429

        ticket2 = create_bind_ticket(openid="o_bind_phone", unionid=None, wx_member_id=None)
        assert_bind_ticket_sms_allowed(ticket2, "13900007733")
        with pytest.raises(HTTPException) as exc2:
            assert_bind_ticket_sms_allowed(ticket2, "13900007744")
        assert exc2.value.status_code == 400


class TestWechatBindSmsApi:
    def test_wechat_bind_sms_respects_ticket_limit(self, client: TestClient, monkeypatch):
        from app.services import sms_service

        monkeypatch.setattr(sms_service, "_check_send_rate", lambda *_a, **_k: None)
        monkeypatch.setattr(sms_service, "_record_send", lambda *_a, **_k: None)

        ticket = create_bind_ticket(openid="o_api_bind", unionid=None, wx_member_id=None)
        phone = "13900007755"
        for _ in range(BIND_SMS_MAX_PER_TICKET):
            res = client.post(
                "/api/auth/wechat/send-bind-sms",
                json={"bind_ticket": ticket, "phone": phone},
            )
            assert res.status_code == 200, res.text
        res = client.post(
            "/api/auth/wechat/send-bind-sms",
            json={"bind_ticket": ticket, "phone": phone},
        )
        assert res.status_code == 429
