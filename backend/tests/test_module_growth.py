"""成长里程碑 pages/growth/index.vue"""


class TestModuleGrowth:
    def test_badges_reflect_assessment(self, client, child_with_assessment):
        uid = child_with_assessment
        badges = client.get(f"/api/growth/badges?user_id={uid}").json()["items"]
        first = next(b for b in badges if b["name"] == "首次测评")
        assert first["earned"] is True

    def test_timeline_has_assessment_event(self, client, child_with_assessment):
        uid = child_with_assessment
        events = client.get(f"/api/growth/timeline?user_id={uid}").json()["items"]
        assert any("天赋测评" in e["title"] for e in events)

    def test_milestones_progress(self, client, user_ready_for_training):
        uid = user_ready_for_training
        plan = client.get(f"/api/training/today?user_id={uid}").json()
        client.post(
            f"/api/training/checkin?user_id={uid}",
            json={"plan_id": plan["plan_id"]},
        )
        ms = client.get(f"/api/growth/milestones?user_id={uid}").json()["items"]
        assert ms[0]["achieved"] is True
        assert "1/7" in ms[1]["progress"]
