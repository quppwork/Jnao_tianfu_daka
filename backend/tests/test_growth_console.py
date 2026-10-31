"""中央电脑 GET /api/growth/console"""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import TrainingPlan, TrainingRecord
from app.services.growth_console_service import board_refresh_window, get_console
from app.services.growth_tier_period import lock_progress


def test_board_refresh_at_midnight():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    cst = ZoneInfo("Asia/Shanghai")
    morning = board_refresh_window(datetime(2026, 9, 12, 1, 0, tzinfo=cst))
    evening = board_refresh_window(datetime(2026, 9, 12, 23, 0, tzinfo=cst))
    assert "2026-09-12T00:00:00" in morning["as_of"]
    assert "2026-09-13T00:00:00" in morning["next_refresh_at"]
    assert morning["as_of"] == evening["as_of"]


def test_get_console_shape(db_session: Session, child_with_assessment: int):
    data = get_console(db_session, child_with_assessment)
    assert data["tier"]["level"] == data["tier"]["overall_tier"]
    assert "筑基期" in data["tier"]["duan_label"] or "开窍期" in data["tier"]["duan_label"] or data["tier"]["level"] >= 1
    assert data["skills_wall"] is None
    assert data["ladder"]["refresh"]["mode"] == "local"
    assert data["ladder"]["me"]["rank"] >= 1
    assert len(data["locks"]) == 4
    assert "today_checked" in data["lcd"]
    assert "streak_days" in data["lcd"]
    assert "bar_pct" in data["xp"]
    assert "month" in data
    assert "days" in data["month"]
    assert "month_minutes" in data["month"]
    assert "replay" in data
    assert len(data["replay"]["scenes"]) == 5
    assert data["replay"]["talent"] is None
    assert "state_line" in data["replay"]
    names = {s["skill"] for s in data["replay"]["scenes"]}
    assert "超脑阅读" in names
    assert "影像追忆" in names


def test_practice_realm_by_days_30():
    from app.services.growth_console_service import _practice_realm

    assert _practice_realm(days_30=0)["full"] == "第一境·完全荒废"
    assert _practice_realm(days_30=5)["full"] == "第二境·三天打鱼"
    assert _practice_realm(days_30=10)["full"] == "第三境·尽力训练"
    assert _practice_realm(days_30=18)["full"] == "第四境·锋芒初现"
    assert _practice_realm(days_30=25)["full"] == "第五境·万法归一"


def test_replay_state_line_uses_xp_not_talent(db_session: Session, child_with_assessment: int):
    uid = child_with_assessment
    today = date.today()
    for i in range(10):
        d = today - timedelta(days=i)
        plan = TrainingPlan(child_user_id=uid, plan_date=d, planned_minutes=30, status="done")
        db_session.add(plan)
        db_session.flush()
        db_session.add(
            TrainingRecord(
                child_user_id=uid,
                plan_id=plan.id,
                train_date=d,
                review_status="approved",
                attitude_pct=90,
            )
        )
    db_session.commit()

    data = get_console(db_session, uid)
    rp = data["replay"]
    assert "尽力训练" in rp["state_line"] or "锋芒初现" in rp["state_line"]
    assert "经验" in rp["state_line"]
    assert "天赋值" not in rp["state_line"]
    assert rp["realm"]["days_30"] >= 10


def test_console_reflects_checkin_streak(db_session: Session, child_with_assessment: int):
    uid = child_with_assessment
    today = date.today()
    for i in range(3):
        d = today - timedelta(days=i)
        plan = TrainingPlan(child_user_id=uid, plan_date=d, planned_minutes=40, status="done")
        db_session.add(plan)
        db_session.flush()
        db_session.add(
            TrainingRecord(
                child_user_id=uid,
                plan_id=plan.id,
                train_date=d,
                review_status="approved",
                attitude_pct=90,
            )
        )
    db_session.commit()

    data = get_console(db_session, uid)
    assert data["lcd"]["today_checked"] is True
    assert data["lcd"]["streak_days"] >= 3
    assert data["lcd"]["total_checkin_days"] >= 3
    assert data["xp"]["process_xp"] >= 120  # 3 * 40


def test_console_api(client: TestClient, child_with_assessment: int):
    uid = child_with_assessment
    res = client.get(f"/api/growth/console?user_id={uid}")
    assert res.status_code == 200
    body = res.json()
    assert body["tier"]["level"] == body["tier"]["overall_tier"]
    assert body["locks"][0]["total"] == 3
    # 默认一段：第一锁亮 1/3
    if body["tier"]["level"] == 1:
        assert body["locks"][0]["filled"] == 1
        assert body["locks"][0]["open"] is False


def test_tier_api_includes_duan_label(client: TestClient, child_with_assessment: int):
    uid = child_with_assessment
    res = client.get(f"/api/growth/tier?user_id={uid}")
    assert res.status_code == 200
    body = res.json()
    assert body["level"] == body["overall_tier"]
    assert "duan_label" in body
