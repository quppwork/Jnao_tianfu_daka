"""天赋测试 pages/talent/index.vue + pages/report/index.vue"""

from fastapi.testclient import TestClient


class TestModuleTalent:
    def test_submit_report(self, client: TestClient, mock_jnao, registered_user):
        uid = registered_user["child_user_id"]
        res = client.post(
            "/api/talent/report",
            json={
                "answer": "1" * 35,
                "uid": 123456,
                "type": 1,
                "child_user_id": uid,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 1
        assert body["data"]["talent"] == "学者"
        assert body["assessment_id"]

        history = client.get(f"/api/talent/assessment/history?user_id={uid}")
        assert history.status_code == 200
        assert len(history.json()["items"]) == 1

        detail = client.get(f"/api/talent/assessment/{body['assessment_id']}?user_id={uid}")
        assert detail.status_code == 200
        assert detail.json()["data"]["talent"] == "学者"

        latest = client.get(f"/api/talent/assessment/latest?user_id={uid}")
        assert latest.status_code == 200
        assert latest.json()["talent_code"] == 1

    def test_delete_assessment_archives(self, client: TestClient, mock_jnao, registered_user, db_session):
        uid = registered_user["child_user_id"]
        res = client.post(
            "/api/talent/report",
            json={"answer": "1" * 35, "uid": 123456, "type": 1, "child_user_id": uid},
        )
        aid = res.json()["assessment_id"]
        del_res = client.delete(f"/api/talent/assessment/{aid}?user_id={uid}")
        assert del_res.status_code == 200
        assert del_res.json()["deleted"] is True

        history = client.get(f"/api/talent/assessment/history?user_id={uid}")
        assert history.json()["items"] == []

        latest = client.get(f"/api/talent/assessment/latest?user_id={uid}")
        assert latest.status_code == 404

        from sqlalchemy import select
        from app.db.models import TalentAssessmentArchive

        archived = db_session.scalar(
            select(TalentAssessmentArchive).where(TalentAssessmentArchive.original_id == aid)
        )
        assert archived is not None
        assert archived.snapshot_json["talent_primary"] == "学者"

    def test_latest_talent_refreshes_pending_plan(self, client, db_session, mock_jnao, registered_user):
        uid = registered_user["child_user_id"]
        client.post(
            "/api/talent/report",
            json={"answer": "1" * 35, "uid": 123456, "type": 1, "child_user_id": uid},
        )
        plan1 = client.get(f"/api/training/today?user_id={uid}").json()
        assert "学" in (plan1["items"][0]["title"] or "")

        mock_jnao["report"].return_value = {
            "id": 124,
            "uid": 123456,
            "type": 1,
            "talent": "赢者",
            "check_talent": "赢者",
            "create_time": "2026-06-24",
            "results": {},
            "property": "[]",
            "AttributeJs": "{}",
            "StateIcon": "",
        }
        client.post(
            "/api/talent/report",
            json={"answer": "0" * 35, "uid": 123456, "type": 1, "child_user_id": uid},
        )

        latest = client.get(f"/api/talent/assessment/latest?user_id={uid}").json()
        assert latest["talent_primary"] == "赢者"

        plan2 = client.get(f"/api/training/today?user_id={uid}").json()
        assert plan2["items"][0]["title"] != plan1["items"][0]["title"]
        assert "赢" in (plan2["items"][0]["title"] or "") or "精力" in (plan2["items"][0]["title"] or "")

        profile = client.get(f"/api/user/profile?user_id={uid}").json()
        assert profile["talent_primary"] == "赢者"
        assert profile["training_level"] == "赢者"

    def test_training_blocked_without_assessment(self, client: TestClient, registered_user):
        uid = registered_user["child_user_id"]
        res = client.get(f"/api/training/today?user_id={uid}")
        assert res.status_code == 403

    def test_child_type_uses_type_1(self, client: TestClient, mock_jnao):
        res = client.post(
            "/api/talent/report",
            json={"answer": "0" * 35, "uid": 1, "type": 1},
        )
        assert res.status_code == 200
        mock_jnao["submit"].assert_called_once()
        assert mock_jnao["submit"].call_args[0][2] == 1
