"""今日训练 API 测试"""

from datetime import date, timedelta

from app.services.training_service import get_or_create_today_plan, submit_checkin


class TestTrainingToday:
    def test_requires_assessment(self, client):
        reg = client.post(
            "/api/auth/register",
            json={"parent_phone": "13900139000", "nickname": "无测评"},
        )
        user_id = reg.json()["child_user_id"]
        res = client.get(f"/api/training/today?user_id={user_id}")
        assert res.status_code == 403

    def test_today_returns_audio(self, client, child_with_assessment, mock_doubao):
        res = client.get(f"/api/training/today?user_id={child_with_assessment}")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "pending"
        assert len(data["items"]) == 1
        assert data["items"][0]["audio_url"]
        assert "学" in (data["items"][0]["title"] or "")
        assert data["report_text"]
        assert not data["report_text"].startswith("今日音频：")

    def test_checkin_completes_plan(self, client, child_with_assessment, mock_doubao):
        today = client.get(f"/api/training/today?user_id={child_with_assessment}").json()
        res = client.post(
            f"/api/training/checkin?user_id={child_with_assessment}",
            json={"plan_id": today["plan_id"]},
        )
        assert res.status_code == 200
        assert res.json()["plan_status"] == "completed"

        progress = client.get(f"/api/training/progress?user_id={child_with_assessment}").json()
        assert progress["today_completed"] is True
        assert progress["total_checkins"] == 1

    def test_continue_same_if_yesterday_incomplete(self, db_session, child_with_assessment):
        yesterday = date.today() - timedelta(days=1)
        plan_y = get_or_create_today_plan(db_session, child_with_assessment, yesterday)
        idx_y = plan_y["content_index"]

        today_plan = get_or_create_today_plan(db_session, child_with_assessment, date.today())
        assert today_plan["content_index"] == idx_y

    def test_next_item_if_yesterday_completed(self, db_session, child_with_assessment):
        yesterday = date.today() - timedelta(days=1)
        plan_y = get_or_create_today_plan(db_session, child_with_assessment, yesterday)
        submit_checkin(db_session, child_with_assessment, plan_id=plan_y["plan_id"])

        today_plan = get_or_create_today_plan(db_session, child_with_assessment, date.today())
        assert today_plan["content_index"] == plan_y["content_index"] + 1


class TestCheckinCrud:
    def test_today_checkins(self, client, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        plan = client.get(f"/api/training/today?user_id={uid}").json()
        client.post(
            f"/api/training/checkin?user_id={uid}",
            json={
                "plan_id": plan["plan_id"],
                "attitude_pct": 80,
                "cards": [{"name": "影像追忆", "time": "1"}],
            },
        )
        res = client.get(f"/api/training/checkin/today?user_id={uid}")
        assert res.status_code == 200
        items = res.json()
        assert len(items) == 1
        assert items[0]["cards"][0]["name"] == "影像追忆"

    def test_update_checkin_cards(self, client, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        plan = client.get(f"/api/training/today?user_id={uid}").json()
        created = client.post(
            f"/api/training/checkin?user_id={uid}",
            json={
                "plan_id": plan["plan_id"],
                "attitude_pct": 60,
                "cards": [
                    {"name": "影像追忆", "time": "1"},
                    {"name": "极速运算", "time": "5", "tag": "口算", "count": "20", "accuracy": "90"},
                ],
            },
        ).json()
        record_id = created["record_id"]

        updated = client.put(
            f"/api/training/checkin/{record_id}?user_id={uid}",
            json={"cards": [{"name": "影像追忆", "time": "2"}]},
        )
        assert updated.status_code == 200
        data = updated.json()
        assert len(data["record"]["cards"]) == 1
        assert data["record"]["cards"][0]["time"] == "2"
        assert "影像追忆" in data["record"]["content"]

    def test_delete_checkin_resets_plan(self, client, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        plan = client.get(f"/api/training/today?user_id={uid}").json()
        created = client.post(
            f"/api/training/checkin?user_id={uid}",
            json={"plan_id": plan["plan_id"], "attitude_pct": 80, "cards": [{"name": "影像追忆", "time": "1"}]},
        ).json()
        record_id = created["record_id"]

        deleted = client.delete(f"/api/training/checkin/{record_id}?user_id={uid}")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True
        assert deleted.json()["plan_status"] == "pending"

        progress = client.get(f"/api/training/progress?user_id={uid}").json()
        assert progress["today_completed"] is False


class TestTrainingWindow:
    def test_set_and_get_window(self, client, child_with_assessment):
        uid = child_with_assessment
        res = client.post(
            f"/api/training/window?user_id={uid}",
            json={"start_time": "09:00", "end_time": "21:00"},
        )
        assert res.status_code == 200
        got = client.get(f"/api/training/window?user_id={uid}")
        assert got.json()["start_time"] == "09:00"

    def test_window_status(self, client, child_with_assessment):
        res = client.get(f"/api/training/window/status?user_id={child_with_assessment}")
        assert res.status_code == 200
        assert "in_window" in res.json()


class TestTalentAssessment:
    def test_latest_assessment(self, client, child_with_assessment):
        res = client.get(f"/api/talent/assessment/latest?user_id={child_with_assessment}")
        assert res.status_code == 200
        assert res.json()["talent_code"] == 1
        assert res.json()["talent_tag"] == "学"

    def test_report_with_child_user_id(self, client, db_session):
        reg = client.post(
            "/api/auth/register",
            json={"parent_phone": "13700137000", "nickname": "测评童"},
        )
        user_id = reg.json()["child_user_id"]
        res = client.post(
            "/api/talent/report",
            json={
                "answer": "1" * 35,
                "uid": 123456,
                "type": 1,
                "child_user_id": user_id,
            },
        )
        assert res.status_code == 200
        latest = client.get(f"/api/talent/assessment/latest?user_id={user_id}")
        assert latest.status_code == 200


class TestTrainingSchedule:
    def test_schedule_requires_assessment(self, client):
        reg = client.post(
            "/api/auth/register",
            json={"parent_phone": "13900139002", "nickname": "无测评排课"},
        )
        user_id = reg.json()["child_user_id"]
        res = client.post(
            f"/api/training/schedule?user_id={user_id}",
            json={"planned_minutes": 45},
        )
        assert res.status_code == 403

    def test_schedule_by_duration(self, client, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        res = client.post(
            f"/api/training/schedule?user_id={uid}",
            json={"planned_minutes": 45},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["planned_minutes"] == 45
        assert len(data["items"]) >= 2
        blocks = {i.get("block") for i in data["items"]}
        assert "A" in blocks
        assert any(i.get("item_type") == "video" for i in data["items"])
        assert any(i.get("item_type") == "audio" for i in data["items"])

    def test_talent_video(self, client, child_with_assessment):
        res = client.get(f"/api/training/video/talent?user_id={child_with_assessment}")
        assert res.status_code == 200
        body = res.json()
        assert body["url"]
        assert body["talent_code"] == 1
        assert body["source"] == "talent_fixed"


class TestResources:
    def test_list_resources(self, client, db_session):
        res = client.get("/api/resources/list?talent_code=1")
        assert res.status_code == 200
        assert res.json()["total"] >= 8
