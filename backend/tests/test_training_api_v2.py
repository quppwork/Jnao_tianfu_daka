"""v2.0 训练 API 集成测试 — schedule → checkin → progress 全链路"""

import pytest


def _auth(uid: int) -> dict:
    return {"headers": {"X-Child-User-Id": str(uid)}}


def _finish_media_if_needed(client, uid: int, item: dict) -> None:
    """有音/视频 URL 时打卡前须上报听完进度。"""
    if not (item.get("audio_url") or item.get("video_url")):
        return
    res = client.post(
        f"/api/training/items/{item['id']}/watch-progress",
        json={"watched_sec": 95, "duration_sec": 100},
        **_auth(uid),
    )
    assert res.status_code == 200, res.text
    assert res.json().get("video_complete") is True


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

    def test_started_cannot_change_minutes(self, client, user_ready_for_training):
        """已开始后改时长 → 403，不重生"""
        uid = user_ready_for_training
        auth = _auth(uid)
        first = client.post("/api/training/schedule", json={"planned_minutes": 20}, **auth)
        assert first.status_code == 200
        plan = first.json()
        item_id = plan["items"][0]["id"]
        # 上报观看进度 → 视为已开始
        wp = client.post(
            f"/api/training/items/{item_id}/watch-progress",
            json={"watched_sec": 30, "duration_sec": 100},
            **auth,
        )
        assert wp.status_code == 200, wp.text
        second = client.post("/api/training/schedule", json={"planned_minutes": 40}, **auth)
        assert second.status_code == 403
        assert "无法更改" in second.json().get("detail", "")

    def test_started_bloated_plan_not_wiped(self, client, user_ready_for_training, db_session):
        """已开始 + 项数超上界：仍返回 existing，不清表"""
        from app.db.models import TrainingItem, TrainingPlan
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        uid = user_ready_for_training
        auth = _auth(uid)
        first = client.post("/api/training/schedule", json={"planned_minutes": 20}, **auth)
        assert first.status_code == 200
        plan_id = first.json()["plan_id"]
        item_id = first.json()["items"][0]["id"]
        client.post(
            f"/api/training/items/{item_id}/watch-progress",
            json={"watched_sec": 10, "duration_sec": 60},
            **auth,
        )
        # 人为塞入超额项，模拟脏结构
        plan = db_session.scalar(
            select(TrainingPlan).options(selectinload(TrainingPlan.items)).where(TrainingPlan.id == plan_id)
        )
        before_count = len(plan.items)
        for i in range(5):
            db_session.add(
                TrainingItem(
                    plan_id=plan_id,
                    sort_order=10 + i,
                    ability_type="audio",
                    title=f"脏数据{i}",
                    checkin_status="pending",
                    instructions='{"skill": "影像追忆", "item_type": "audio"}',
                )
            )
        db_session.commit()
        again = client.post("/api/training/schedule", json={"planned_minutes": 20}, **auth)
        assert again.status_code == 200
        assert again.json().get("schedule_mode") == "existing"
        plan2 = db_session.scalar(
            select(TrainingPlan).options(selectinload(TrainingPlan.items)).where(TrainingPlan.id == plan_id)
        )
        assert len(plan2.items) == before_count + 5


class TestCheckinV2:
    """POST /api/training/checkin — 打卡 + Tier 晋级判定"""

    def test_checkin_requires_media_complete(self, client, user_ready_for_training, db_session):
        """纯音频项未听完不可打卡；有视频的项不限制进度。"""
        from app.db.models import TrainingItem

        uid = user_ready_for_training
        sched = client.post("/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid))
        plan = sched.json()
        item = plan["items"][0]
        row = db_session.get(TrainingItem, item["id"])
        row.audio_url = "https://example.com/a.mp3"
        row.video_url = None
        db_session.commit()

        blocked = client.post("/api/training/checkin", json={
            "plan_id": plan["plan_id"], "item_id": item["id"],
            "cards": [{"name": "超脑阅读", "time": "2.5", "wordCount": "900"}],
        }, **_auth(uid))
        assert blocked.status_code == 403
        assert "听完" in blocked.json().get("detail", "")

        ok_watch = client.post(
            f"/api/training/items/{item['id']}/watch-progress",
            json={"watched_sec": 95, "duration_sec": 100},
            **_auth(uid),
        )
        assert ok_watch.status_code == 200
        res = client.post("/api/training/checkin", json={
            "plan_id": plan["plan_id"], "item_id": item["id"],
            "cards": [{"name": "超脑阅读", "time": "2.5", "wordCount": "900"}],
        }, **_auth(uid))
        assert res.status_code == 200

    def test_video_item_checkin_without_watch(self, client, user_ready_for_training, db_session):
        """仅视频的训练项不要求看完即可打卡。"""
        from app.db.models import TrainingItem

        uid = user_ready_for_training
        sched = client.post("/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid))
        plan = sched.json()
        item = plan["items"][0]
        row = db_session.get(TrainingItem, item["id"])
        row.video_url = "https://example.com/a.mp4"
        row.audio_url = None
        db_session.commit()

        res = client.post("/api/training/checkin", json={
            "plan_id": plan["plan_id"], "item_id": item["id"],
            "cards": [{"name": "超脑阅读", "time": "2.5", "wordCount": "900"}],
        }, **_auth(uid))
        assert res.status_code == 200

    def test_video_watch_does_not_unlock_audio_checkin(self, client, user_ready_for_training, db_session):
        """音视频并存时，看完视频不能代替听完音频。"""
        from app.db.models import TrainingItem

        uid = user_ready_for_training
        auth = _auth(uid)
        sched = client.post("/api/training/schedule", json={"planned_minutes": 20}, **auth)
        plan = sched.json()
        item = plan["items"][0]
        row = db_session.get(TrainingItem, item["id"])
        row.audio_url = "https://example.com/a.mp3"
        row.video_url = "https://example.com/a.mp4"
        db_session.commit()

        client.post(
            f"/api/training/items/{item['id']}/watch-progress",
            json={"watched_sec": 95, "duration_sec": 100, "media": "video"},
            **auth,
        )
        blocked = client.post("/api/training/checkin", json={
            "plan_id": plan["plan_id"], "item_id": item["id"],
            "cards": [{"name": "超脑阅读", "time": "2.5", "wordCount": "900"}],
        }, **auth)
        assert blocked.status_code == 403

        client.post(
            f"/api/training/items/{item['id']}/watch-progress",
            json={"watched_sec": 95, "duration_sec": 100, "media": "audio"},
            **auth,
        )
        ok = client.post("/api/training/checkin", json={
            "plan_id": plan["plan_id"], "item_id": item["id"],
            "cards": [{"name": "超脑阅读", "time": "2.5", "wordCount": "900"}],
        }, **auth)
        assert ok.status_code == 200

    def test_checkin_pass(self, client, user_ready_for_training):
        uid = user_ready_for_training
        sched = client.post("/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid))
        plan = sched.json()
        item = plan["items"][0]
        _finish_media_if_needed(client, uid, item)
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
        _finish_media_if_needed(client, uid, plan["items"][0])
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
            _finish_media_if_needed(client, uid, plan["items"][1])
            res = client.post("/api/training/checkin", json={
                "plan_id": plan["plan_id"], "item_id": plan["items"][1]["id"],
                "cards": [{"name": "影像追忆", "wordCount": "2000", "accuracy": "80"}],
            }, **_auth(uid))
            assert res.status_code in (400, 403, 422)

    def test_today_list_after_checkin(self, client, user_ready_for_training):
        uid = user_ready_for_training
        sched = client.post("/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid))
        plan = sched.json()
        _finish_media_if_needed(client, uid, plan["items"][0])
        client.post("/api/training/checkin", json={
            "plan_id": plan["plan_id"], "item_id": plan["items"][0]["id"],
            "cards": [{"name": "超脑阅读", "time": "2.5", "wordCount": "900"}],
        }, **_auth(uid))
        res = client.get("/api/training/checkin/today", **_auth(uid))
        assert res.status_code == 200
        assert len(res.json()) >= 1

    def test_update_checkin_after_submit(self, client, user_ready_for_training):
        """再次提交同 block 走 PUT，v2.0 应重算进度而非 ImportError 500"""
        uid = user_ready_for_training
        sched = client.post("/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid))
        plan = sched.json()
        _finish_media_if_needed(client, uid, plan["items"][0])
        created = client.post("/api/training/checkin", json={
            "plan_id": plan["plan_id"], "item_id": plan["items"][0]["id"],
            "cards": [{"name": "超脑阅读", "time": "1", "wordCount": "1000"}],
        }, **_auth(uid))
        assert created.status_code == 200
        record_id = created.json()["record_id"]
        updated = client.put(f"/api/training/checkin/{record_id}", json={
            "cards": [{"name": "超脑阅读", "time": "2", "wordCount": "1200"}],
        }, **_auth(uid))
        assert updated.status_code == 200
        assert updated.json().get("plan_status")


class TestElectiveV2:
    """选修弹窗"""

    def test_list_three_offers(self, client):
        res = client.get("/api/training/elective/list?planned_minutes=120")
        assert res.status_code == 200
        skills = {o["skill"] for o in res.json()["offers"]}
        assert {"精力恢复", "多元感知", "高效作业"}.issubset(skills)
        assert len(res.json()["offers"]) >= 3

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
        _finish_media_if_needed(client, uid, plan["items"][0])
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
        _finish_media_if_needed(client, uid, item)
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
        _finish_media_if_needed(client, uid, plan["items"][0])
        res = client.post("/api/training/checkin", json={
            "plan_id": plan["plan_id"], "item_id": plan["items"][0]["id"],
            "cards": [{"name": "超脑阅读", "time": "10", "wordCount": "100"}],
        }, **_auth(uid))
        assert res.status_code == 200
        tp = res.json().get("training_progress") or {}
        sr = (tp.get("skill_results") or {}).get("超脑阅读", {})
        assert sr.get("passed") is False
