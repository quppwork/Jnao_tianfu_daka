"""成长里程碑 pages/growth/index.vue"""


class TestModuleGrowth:
    def test_badges_reflect_assessment(self, client, child_with_assessment):
        uid = child_with_assessment
        badges = client.get(f"/api/growth/badges?user_id={uid}").json()["items"]
        first = next(b for b in badges if b["name"] == "首次测评")
        assert first["earned"] is True
        assert first.get("earned_at")

    def test_timeline_has_assessment_event(self, client, child_with_assessment):
        uid = child_with_assessment
        events = client.get(f"/api/growth/timeline?user_id={uid}").json()["items"]
        assert any("天赋测评" in e["title"] for e in events)
        assert events[0]["type"] == "assessment"

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

    def test_summary(self, client, child_with_assessment):
        uid = child_with_assessment
        data = client.get(f"/api/growth/summary?user_id={uid}").json()
        assert data["talent_primary"] == "学者"
        assert data["badges_earned"] >= 1
        assert data["honor_level"] == "入门学员"

    def test_share_text(self, client, child_with_assessment):
        uid = child_with_assessment
        data = client.get(f"/api/growth/share?user_id={uid}").json()
        assert "成长" in data["title"]
        assert "学者" in data["text"]
        assert len(data["highlights"]) >= 2

    def test_qa_badge_after_question(self, client, user_ready_for_training, mock_doubao):
        uid = user_ready_for_training
        client.post(
            f"/api/qa/chat?user_id={uid}",
            json={"message": "1+1等于几", "subject": "数学"},
        )
        badges = client.get(f"/api/growth/badges?user_id={uid}").json()["items"]
        qa_badge = next(b for b in badges if b["name"] == "答疑新星")
        assert qa_badge["earned"] is True

    def test_timeline_limit(self, client, child_with_assessment):
        uid = child_with_assessment
        events = client.get(f"/api/growth/timeline?user_id={uid}&limit=1").json()["items"]
        assert len(events) == 1
