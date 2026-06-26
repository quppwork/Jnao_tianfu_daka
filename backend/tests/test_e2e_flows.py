"""端到端用户流程 — 对应前端完整使用路径"""

from datetime import date, timedelta


class TestE2EUserFlows:
    """模拟真实用户从注册到训练打卡的完整链路"""

    def test_full_mvp_loop(self, client, mock_jnao, mock_doubao):
        # 1. 注册
        reg = client.post(
            "/api/auth/register",
            json={"parent_phone": "13700001111", "nickname": "端到端童"},
        )
        uid = reg.json()["child_user_id"]

        # 2. 首页咨询
        guide = client.post(f"/api/guide/chat?user_id={uid}", json={"message": "怎么开始？"})
        assert guide.json()["reply"]

        # 3. 天赋测评
        report = client.post(
            "/api/talent/report",
            json={"answer": "1" * 35, "uid": uid, "type": 1, "child_user_id": uid},
        )
        assert report.json()["data"]["talent"]

        # 4. 今日训练（进入即生成方案）
        today = client.get(f"/api/training/today?user_id={uid}")
        assert today.status_code == 200
        plan_id = today.json()["plan_id"]
        assert plan_id
        assert len(today.json()["items"]) >= 2

        # 5. AI 报告
        rep = client.get(f"/api/training/report/today?user_id={uid}")
        assert rep.json()["report_text"]

        # 6. 打卡（A/B 各一次）
        items = today.json()["items"]
        a_item = next(i for i in items if i.get("block") == "A")
        b_item = next(i for i in items if i.get("block") == "B")
        for it in (a_item, b_item):
            chk = client.post(
                f"/api/training/checkin?user_id={uid}",
                json={"plan_id": plan_id, "item_id": it["id"], "cards": [{"name": "影像追忆", "time": "1"}]},
            )
            assert chk.status_code == 200
        assert chk.json()["plan_status"] == "completed"

        # 7. 学科答疑
        qa = client.post(
            f"/api/qa/chat?user_id={uid}",
            json={"message": "3+5=?", "subject": "数学"},
        )
        assert qa.json()["reply"]

        # 8. 成长数据
        badges = client.get(f"/api/growth/badges?user_id={uid}").json()["items"]
        assert any(b["name"] == "首次测评" and b["earned"] for b in badges)

        # 9. 健康检查含数据库
        health = client.get("/api/health").json()
        assert health["integrations"]["mysql"]["connected"] is True

    def test_day2_new_content_after_checkin(self, client, db_session, mock_jnao):
        from app.db.models import TrainingPlan
        from app.services.assessment_service import save_assessment
        from app.services.auth_service import register_child
        from app.services.training_day import get_training_day
        from app.services.training_service import get_or_create_today_plan

        user = register_child(db_session, parent_phone="13700002222", nickname="次日童")
        save_assessment(
            db_session,
            child_user_id=user.id,
            jnao_record_id="r2",
            answer_bitstring="1" * 35,
            test_type=1,
            report={"talent": "学者", "create_time": "2026-06-18"},
        )
        uid = user.id

        d1 = get_training_day() - timedelta(days=1)
        p1 = get_or_create_today_plan(db_session, uid, d1)
        plan = db_session.get(TrainingPlan, p1["plan_id"])
        plan.status = "completed"
        for item in plan.items:
            item.checkin_status = "done"
        db_session.commit()

        p2 = client.get(f"/api/training/today?user_id={uid}").json()
        assert p2["plan_id"] > 0
        assert p2["content_index"] == p1["content_index"] + 1
