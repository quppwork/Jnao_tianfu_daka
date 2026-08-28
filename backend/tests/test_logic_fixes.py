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
        with patch("app.services.training.service._user_now", return_value=t0):
            with patch("app.services.training.service._today_for", return_value=plan_date):
                first = _refresh_volatile_plan_fields(db_session, user.id, plan_date, stale)
        with patch("app.services.training.service._user_now", return_value=t1):
            with patch("app.services.training.service._today_for", return_value=plan_date):
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

        with patch("app.services.training.service._user_now", return_value=now):
            with patch("app.services.training.service._today_for", return_value=plan_date):
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


class TestOpenTodaySmoothTransition:
    """开放今日训练：已开练沿用现场，未开练才走待确认。"""

    def _make_plan(self, db_session: Session, *, watch_pct: float = 0, minutes: int = 60, suffix: str = "a"):
        from app.db.models import TrainingItem

        user = auth_service.register_child(
            db_session,
            parent_phone=f"1390000881{suffix}",
            nickname="过渡童",
            login_name=f"smooth_kid_{suffix}",
            password="123456",
        )
        plan_date = date(2026, 8, 13)
        plan = TrainingPlan(
            child_user_id=user.id,
            plan_date=plan_date,
            level="A",
            report_text="",
            planned_minutes=minutes,
            status="pending",
        )
        db_session.add(plan)
        db_session.flush()
        item = TrainingItem(
            plan_id=plan.id,
            sort_order=1,
            title="超脑阅读",
            duration_min=10,
            audio_url="https://example.com/a.mp3",
            checkin_status="pending",
            watch_progress={"pct": watch_pct} if watch_pct else None,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(plan)
        return user, plan, plan_date

    def test_unstarted_plan_is_pending_confirm(self, db_session: Session):
        from unittest.mock import patch

        from app.services.training_service import _plan_to_response

        user, plan, plan_date = self._make_plan(db_session, suffix="1")
        now = datetime(2026, 8, 13, 10, 0, 0, tzinfo=TZ)
        with patch("app.services.training.service._user_now", return_value=now):
            with patch("app.services.training.service._today_for", return_value=plan_date):
                out = _plan_to_response(plan, now=now, db=db_session)
        assert out["timer_phase"] == "setup"
        assert out["pending_confirm"] is True

    def test_started_without_window_heals_to_running(self, db_session: Session):
        from unittest.mock import patch

        from app.services.training_service import (
            _heal_started_plan_missing_window,
            _plan_to_response,
            get_training_window,
        )

        user, plan, plan_date = self._make_plan(db_session, watch_pct=15, suffix="2")
        now = datetime(2026, 8, 13, 10, 0, 0, tzinfo=TZ)
        with patch("app.services.training.service._user_now", return_value=now):
            with patch("app.services.training.service._today_for", return_value=plan_date):
                healed = _heal_started_plan_missing_window(db_session, user.id, plan)
                out = _plan_to_response(plan, now=now, db=db_session)
        assert healed is True
        assert get_training_window(db_session, user.id, plan_date) is not None
        assert out["timer_phase"] == "running"
        assert out["pending_confirm"] is False

    def test_unstarted_plan_does_not_heal_window(self, db_session: Session):
        from unittest.mock import patch

        from app.services.training_service import (
            _heal_started_plan_missing_window,
            get_training_window,
        )

        user, plan, plan_date = self._make_plan(db_session, suffix="3")
        now = datetime(2026, 8, 13, 10, 0, 0, tzinfo=TZ)
        with patch("app.services.training.service._user_now", return_value=now):
            with patch("app.services.training.service._today_for", return_value=plan_date):
                healed = _heal_started_plan_missing_window(db_session, user.id, plan)
        assert healed is False
        assert get_training_window(db_session, user.id, plan_date) is None


class TestVideoProgressNotGated:
    def test_video_only_complete_without_watch(self):
        from types import SimpleNamespace

        from app.services.training_service import is_item_media_complete

        item = SimpleNamespace(
            video_url="https://example.com/a.mp4",
            audio_url=None,
            ability_type="video",
            instructions='{"skill":"开口窍","item_type":"video"}',
            watch_progress={"pct": 0},
        )
        assert is_item_media_complete(item) is True

    def test_audio_plus_video_still_needs_audio(self):
        from types import SimpleNamespace

        from app.services.training_service import is_item_media_complete

        item = SimpleNamespace(
            video_url="https://example.com/a.mp4",
            audio_url="https://example.com/a.mp3",
            ability_type="audio",
            instructions='{"skill":"超脑阅读","item_type":"required"}',
            watch_progress={"pct": 0, "video": {"pct": 100}},
        )
        assert is_item_media_complete(item) is False
        item.watch_progress = {"pct": 90, "audio": {"pct": 90}, "video": {"pct": 10}}
        assert is_item_media_complete(item) is True

    def test_audio_only_still_needs_watch(self):
        from types import SimpleNamespace

        from app.services.training_service import is_item_media_complete

        item = SimpleNamespace(
            video_url=None,
            audio_url="https://example.com/a.mp3",
            ability_type="audio",
            instructions='{"skill":"影像追忆","item_type":"audio"}',
            watch_progress={"pct": 10},
        )
        assert is_item_media_complete(item) is False

