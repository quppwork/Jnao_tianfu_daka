"""逻辑漏洞修复回归测试"""

from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ChildUser, TrainingPlan
from app.services import auth_service
from app.services.training_day import TZ
from app.services.training_service import (
    _get_plan_by_date,
    _resolve_today_plan,
    _time_in_training_window,
    get_window_status,
)


class TestAuthDeps:
    def test_authenticated_user_fails_closed_on_db_error(self):
        import inspect
        from app.core import deps

        src = inspect.getsource(deps.get_authenticated_user)
        assert "503" in src
        assert "降级" not in src


class TestTrainingWindow:
    def test_cross_midnight_window(self):
        assert _time_in_training_window(time(22, 0), time(6, 0), time(23, 0)) is True
        assert _time_in_training_window(time(22, 0), time(6, 0), time(3, 0)) is True
        assert _time_in_training_window(time(22, 0), time(6, 0), time(12, 0)) is False

    def test_same_day_window(self):
        assert _time_in_training_window(time(9, 0), time(18, 0), time(12, 0)) is True
        assert _time_in_training_window(time(9, 0), time(18, 0), time(20, 0)) is False

    def test_refresh_volatile_plan_fields_updates_timer(self, db_session: Session):
        from datetime import datetime
        from unittest.mock import patch

        from app.db.models import TrainingItem
        from app.services.training_service import (
            _refresh_volatile_plan_fields,
            set_training_window,
        )

        user = auth_service.register_child(
            db_session,
            parent_phone="13900007703",
            nickname="计时童",
            login_name="timer_kid",
            password="123456",
        )
        plan_date = date(2026, 7, 8)
        plan = TrainingPlan(
            child_user_id=user.id,
            plan_date=plan_date,
            level="A",
            report_text="",
            planned_minutes=60,
            status="pending",
        )
        db_session.add(plan)
        db_session.flush()
        db_session.add(
            TrainingItem(
                plan_id=plan.id,
                sort_order=1,
                title="训练项",
                duration_min=10,
                checkin_status="pending",
            )
        )
        db_session.commit()
        set_training_window(db_session, user.id, "10:00:00", "11:00:00", train_date=plan_date)

        stale = {
            "plan_id": plan.id,
            "planned_minutes": 60,
            "items": [{"id": 1, "title": "训练项"}],
            "timer_phase": "running",
            "timer_remaining_seconds": 3600,
            "timer_end_at": "2026-07-08T11:00:00+08:00",
        }

        t0 = datetime(2026, 7, 8, 10, 0, 0, tzinfo=TZ)
        t1 = datetime(2026, 7, 8, 10, 10, 0, tzinfo=TZ)
        with patch("app.services.training_service._user_now", return_value=t0):
            with patch("app.services.training_service._today_for", return_value=plan_date):
                first = _refresh_volatile_plan_fields(db_session, user.id, plan_date, stale)
        with patch("app.services.training_service._user_now", return_value=t1):
            with patch("app.services.training_service._today_for", return_value=plan_date):
                second = _refresh_volatile_plan_fields(db_session, user.id, plan_date, stale)

        assert first["timer_remaining_seconds"] == 3600
        assert second["timer_remaining_seconds"] == 3000


class TestStalePlanCleanup:
    def test_stale_plan_deleted_on_resolve(self, db_session: Session):
        from unittest.mock import patch

        user = auth_service.register_child(
            db_session,
            parent_phone="13900007701",
            nickname="方案童",
            login_name="plan_kid",
            password="123456",
        )
        plan_date = date(2026, 7, 7)
        plan = TrainingPlan(
            child_user_id=user.id,
            plan_date=plan_date,
            level="视觉",
            report_text="",
            status="pending",
        )
        db_session.add(plan)
        db_session.commit()
        db_session.refresh(plan)
        plan_id = plan.id

        # 日切窗口 4:00–4:05 内同训练日方案视为 stale
        now = datetime(2026, 7, 7, 4, 2, 0, tzinfo=TZ).replace(tzinfo=None)

        with patch("app.services.training_service._user_now", return_value=now):
            with patch("app.services.training_service._today_for", return_value=plan_date):
                result = _resolve_today_plan(db_session, user.id, plan_date)

        assert result is None
        assert db_session.get(TrainingPlan, plan_id) is None

    def test_get_plan_by_date_prefers_newest(self, db_session: Session):
        user = auth_service.register_child(
            db_session,
            parent_phone="13900007702",
            nickname="双方案童",
            login_name="dup_plan",
            password="123456",
        )
        d = date(2026, 7, 6)
        old = TrainingPlan(child_user_id=user.id, plan_date=d, level="A", report_text="", status="pending")
        new = TrainingPlan(child_user_id=user.id, plan_date=d, level="B", report_text="", status="pending")
        db_session.add_all([old, new])
        db_session.commit()
        db_session.refresh(old)
        db_session.refresh(new)

        picked = _get_plan_by_date(db_session, user.id, d)
        assert picked is not None
        assert picked.id == new.id
        assert picked.level == "B"


class TestAdminArchiveFixes:
    def _admin_auth(self, client: TestClient) -> dict:
        data = client.post(
            "/api/admin/login",
            json={"login_name": "pyx", "password": "123456"},
        ).json()
        return {
            "params": {"user_id": data["child_user_id"]},
            "headers": {
                "X-Child-User-Id": str(data["child_user_id"]),
                "X-Session-Token": data["session_token"],
            },
        }

    def test_delete_child_idempotent(self, client: TestClient, db_session: Session):
        from tests.test_parent_auth import STRONG_PWD, _parent_auth, _register_parent

        auth = self._admin_auth(client)
        parent = _register_parent(client, "13900007703", password=STRONG_PWD)
        pauth = _parent_auth(parent)
        child = client.post(
            "/api/parent/children",
            json={"login_name": "arch_kid", "nickname": "归档童", "password": "XiaoMing1"},
            **pauth,
        ).json()
        cid = child["id"]
        assert client.delete(f"/api/admin/children/{cid}", **auth).status_code == 200
        res = client.delete(f"/api/admin/children/{cid}", **auth)
        assert res.status_code == 410

        archived = db_session.get(ChildUser, cid)
        assert archived.account_status == "removed"
        assert archived.parent_phone  # 保留原手机号，不再改写 __deleted_

    def test_unbind_returns_warning(self, client: TestClient, db_session: Session):
        from tests.test_parent_auth import STRONG_PWD, _parent_auth, _register_parent

        auth = self._admin_auth(client)
        parent = _register_parent(client, "13900007704", password=STRONG_PWD)
        pauth = _parent_auth(parent)
        child = client.post(
            "/api/parent/children",
            json={"login_name": "warn_kid", "nickname": "解绑童", "password": "XiaoMing1"},
            **pauth,
        ).json()
        res = client.delete(f"/api/admin/children/{child['id']}/bind", **auth)
        assert res.status_code == 200
        assert "warning" in res.json()
