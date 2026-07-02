"""v2.0 训练 API 集成测试 — schedule → checkin → progress 全链路"""

import pytest


def _auth(uid: int) -> dict:
    return {"headers": {"X-Child-User-Id": str(uid)}}


class TestScheduleV2:
    """POST /api/training/schedule — 公式引擎排课"""

    def test_schedule_20min(self, client, user_ready_for_training):
        uid = user_ready_for_training
        res = client.post("/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid))
        assert res.status_code == 200
        data = res.json()
        assert data["planned_minutes"] == 20
        assert len(data["items"]) == 1

    def test_schedule_40min(self, client, user_ready_for_training):
        uid = user_ready_for_training
        res = client.post("/api/training/schedule", json={"planned_minutes": 40}, **_auth(uid))
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) == 2

    def test_schedule_120min(self, client, user_ready_for_training):
        uid = user_ready_for_training
        res = client.post("/api/training/schedule", json={"planned_minutes": 120}, **_auth(uid))
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) >= 3

    def test_schedule_returns_overall_tier(self, client, user_ready_for_training):
        uid = user_ready_for_training
        res = client.post("/api/training/schedule", json={"planned_minutes": 40}, **_auth(uid))
        assert res.status_code == 200
        assert res.json().get("overall_tier") == 1

    def test_schedule_no_talent_blocked(self, client, registered_user):
        uid = registered_user["child_user_id"]
        res = client.post("/api/training/schedule", json={"planned_minutes": 40}, **_auth(uid))
        assert res.status_code in (403, 422), f"Got {res.status_code}"

    def test_schedule_items_sequential(self, client, user_ready_for_training):
        uid = user_ready_for_training
        res = client.post("/api/training/schedule", json={"planned_minutes": 90}, **_auth(uid))
        assert res.status_code == 200
        orders = [item["sort_order"] for item in res.json()["items"]]
        assert orders == sorted(orders)

    def test_schedule_minutes_too_low(self, client, user_ready_for_training):
        uid = user_ready_for_training
        res = client.post("/api/training/schedule", json={"planned_minutes": 3}, **_auth(uid))
        assert res.status_code in (400, 422)


class TestCheckinV2:
    """POST /api/training/checkin — 打卡 + Tier 晋级判定"""

    def test_checkin_pass(self, client, user_ready_for_training):
        uid = user_ready_for_training
        sched = client.post("/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid))
        plan = sched.json()
        item = plan["items"][0]
        res = client.post("/api/training/checkin", json={
            "plan_id": plan["plan_id"], "item_id": item["id"],
            "cards": [{"name": "超脑阅读", "time": "2.5", "wordCount": "900"}],
        }, **_auth(uid))
        assert res.status_code == 200
        assert res.json()["record_id"] > 0

    def test_checkin_fail(self, client, user_ready_for_training):
        uid = user_ready_for_training
        sched = client.post("/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid))
        plan = sched.json()
        res = client.post("/api/training/checkin", json={
            "plan_id": plan["plan_id"], "item_id": plan["items"][0]["id"],
            "cards": [{"name": "超脑阅读", "time": "10", "wordCount": "100"}],
        }, **_auth(uid))
        assert res.status_code == 200

    def test_sequential_order(self, client, user_ready_for_training):
        uid = user_ready_for_training
        sched = client.post("/api/training/schedule", json={"planned_minutes": 120}, **_auth(uid))
        plan = sched.json()
        if len(plan["items"]) >= 2:
            res = client.post("/api/training/checkin", json={
                "plan_id": plan["plan_id"], "item_id": plan["items"][1]["id"],
                "cards": [{"name": "影像追忆", "wordCount": "2000", "accuracy": "80"}],
            }, **_auth(uid))
            assert res.status_code in (400, 403, 422)

    def test_today_list_after_checkin(self, client, user_ready_for_training):
        uid = user_ready_for_training
        sched = client.post("/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid))
        plan = sched.json()
        client.post("/api/training/checkin", json={
            "plan_id": plan["plan_id"], "item_id": plan["items"][0]["id"],
            "cards": [{"name": "超脑阅读", "time": "2.5", "wordCount": "900"}],
        }, **_auth(uid))
        res = client.get("/api/training/checkin/today", **_auth(uid))
        assert res.status_code == 200
        assert len(res.json()) >= 1


class TestElectiveV2:
    """选修弹窗"""

    def test_list_three_offers(self, client):
        res = client.get("/api/training/elective/list?planned_minutes=120")
        assert res.status_code == 200
        assert len(res.json()["offers"]) == 3

    def test_energy_disabled_under_8h(self, client):
        res = client.get("/api/training/elective/list?planned_minutes=120")
        offers = {o["skill"]: o for o in res.json()["offers"]}
        assert offers["精力恢复"]["available"] is False

    def test_energy_enabled_over_8h(self, client):
        res = client.get("/api/training/elective/list?planned_minutes=500")
        offers = {o["skill"]: o for o in res.json()["offers"]}
        assert offers["精力恢复"]["available"] is True

    def test_perception_always_available(self, client):
        res = client.get("/api/training/elective/list?planned_minutes=20")
        offers = {o["skill"]: o for o in res.json()["offers"]}
        assert offers["多元感知"]["available"] is True
        assert offers["多元感知"]["has_checkin"] is True


class TestProgressV2:
    """GET /api/training/progress"""

    def test_progress_after_schedule(self, client, user_ready_for_training):
        uid = user_ready_for_training
        client.post("/api/training/schedule", json={"planned_minutes": 40}, **_auth(uid))
        res = client.get("/api/training/progress", **_auth(uid))
        assert res.status_code == 200


class TestTodayV2:
    """GET /api/training/today"""

    def test_today_after_schedule(self, client, user_ready_for_training):
        uid = user_ready_for_training
        client.post("/api/training/schedule", json={"planned_minutes": 40}, **_auth(uid))
        res = client.get("/api/training/today", **_auth(uid))
        assert res.status_code == 200
        data = res.json()
        assert data.get("overall_tier") == 1

    def test_today_without_schedule(self, client, user_ready_for_training):
        uid = user_ready_for_training
        res = client.get("/api/training/today", **_auth(uid))
        assert res.status_code == 200


class TestHistoryV2:
    """GET /api/training/history"""

    def test_history_after_checkin(self, client, user_ready_for_training):
        uid = user_ready_for_training
        sched = client.post("/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid))
        plan = sched.json()
        client.post("/api/training/checkin", json={
            "plan_id": plan["plan_id"], "item_id": plan["items"][0]["id"],
            "cards": [{"name": "超脑阅读", "time": "2.5", "wordCount": "900"}],
        }, **_auth(uid))
        res = client.get("/api/training/history", **_auth(uid))
        assert res.status_code == 200
        assert len(res.json()["items"]) >= 1


class TestConsecutivePassFlowV2:
    """单日单次打卡验证（跨天晋级见 unit tests）"""

    def test_single_pass_increments_count(self, client, user_ready_for_training):
        uid = user_ready_for_training
        sched = client.post("/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid))
        plan = sched.json()
        item = plan["items"][0]
        res = client.post("/api/training/checkin", json={
            "plan_id": plan["plan_id"], "item_id": item["id"],
            "cards": [{"name": "超脑阅读", "time": "2", "wordCount": "900"}],
        }, **_auth(uid))
        assert res.status_code == 200
        tp = res.json().get("training_progress") or {}
        sr = (tp.get("skill_results") or {}).get("超脑阅读", {})
        assert sr.get("passed") is True

    def test_fail_resets_count(self, client, user_ready_for_training):
        uid = user_ready_for_training
        sched = client.post("/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid))
        plan = sched.json()
        res = client.post("/api/training/checkin", json={
            "plan_id": plan["plan_id"], "item_id": plan["items"][0]["id"],
            "cards": [{"name": "超脑阅读", "time": "10", "wordCount": "100"}],
        }, **_auth(uid))
        assert res.status_code == 200
        tp = res.json().get("training_progress") or {}
        sr = (tp.get("skill_results") or {}).get("超脑阅读", {})
        assert sr.get("passed") is False
