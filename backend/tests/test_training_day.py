"""训练日边界 — 凌晨4点换日"""

from datetime import datetime, timedelta, timezone

from app.services.training_day import RESET_HOUR, get_training_day, is_plan_day_locked, next_unlock_at

TZ = timezone(timedelta(hours=8))


class TestTrainingDay:
    def test_before_4am_counts_as_previous_day(self):
        tz = TZ
        now = datetime(2026, 6, 26, 2, 30, tzinfo=tz)
        assert get_training_day(now).isoformat() == "2026-06-25"

    def test_after_4am_same_calendar_day(self):
        tz = TZ
        now = datetime(2026, 6, 26, 10, 0, tzinfo=tz)
        assert get_training_day(now).isoformat() == "2026-06-26"

    def test_unlock_at_next_day_4am(self):
        tz = TZ
        now = datetime(2026, 6, 26, 22, 0, tzinfo=tz)
        unlock = next_unlock_at(now)
        assert unlock.hour == RESET_HOUR
        assert unlock.date().isoformat() == "2026-06-27"

    def test_day_transition_window(self):
        from app.services.training_day import is_in_day_transition, is_new_day_ready

        tz = TZ
        assert is_in_day_transition(datetime(2026, 6, 26, 4, 2, tzinfo=tz)) is True
        assert is_new_day_ready(datetime(2026, 6, 26, 4, 2, tzinfo=tz)) is False
        assert is_in_day_transition(datetime(2026, 6, 26, 4, 6, tzinfo=tz)) is False

    def test_stale_plan_after_day_roll(self):
        from datetime import date

        from app.services.training_day import is_plan_stale

        tz = TZ
        now = datetime(2026, 6, 26, 10, 0, tzinfo=tz)
        plan = _Plan(date(2026, 6, 25), "completed")
        assert is_plan_stale(plan, now=now) is True


class _Plan:
    def __init__(self, plan_date, status):
        self.plan_date = plan_date
        self.status = status


class TestPlanDayLock:
    def test_completed_today_plan_locked(self):
        from datetime import date

        tz = TZ
        now = datetime(2026, 6, 26, 12, 0, tzinfo=tz)
        plan = _Plan(date(2026, 6, 26), "completed")
        assert is_plan_day_locked(plan, now=now) is True

    def test_pending_not_locked(self):
        from datetime import date

        tz = TZ
        now = datetime(2026, 6, 26, 12, 0, tzinfo=tz)
        plan = _Plan(date(2026, 6, 26), "pending")
        assert is_plan_day_locked(plan, now=now) is False
