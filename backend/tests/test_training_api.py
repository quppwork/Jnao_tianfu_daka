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

    def test_entry_without_assessment(self, client, registered_user):
        uid = registered_user["child_user_id"]
        res = client.get(f"/api/training/entry?user_id={uid}")
        assert res.status_code == 200
        body = res.json()
        assert body["needs_assessment"] is True
        assert body["has_assessment"] is False

    def test_entry_with_assessment(self, client, child_with_assessment):
        res = client.get(f"/api/training/entry?user_id={child_with_assessment}")
        assert res.status_code == 200
        body = res.json()
        assert body["has_assessment"] is True
        assert body["talent_code"] is not None

    def test_skip_ai_returns_fast_placeholder(self, client, child_with_assessment, mock_doubao):
        res = client.get(f"/api/training/today?user_id={child_with_assessment}&skip_ai=1")
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) == 1
        assert data["report_text"].startswith("今日音频：")

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


class TestSequentialCheckinFlow:
    """训练 A→B 顺序打卡全链路测试

    覆盖: 注册→测评→排课→A打卡→B解锁→B打卡→完成
    同时验证本次修复的 bug: B 打卡时误传 items[0].id (A 项 ID) 被正确拒绝
    """

    def _setup_user_with_schedule(self, client):
        """注册 + 测评 + 排课，返回 (uid, items, plan_id)"""
        import random
        phone = f"138888{random.randint(10000, 99999)}"
        # 1. 注册
        reg = client.post(
            "/api/auth/register",
            json={"parent_phone": phone, "nickname": "顺序打卡童"},
        )
        uid = reg.json()["child_user_id"]

        # 2. 天赋测评
        client.post(
            "/api/talent/report",
            json={
                "answer": "1" * 35,
                "uid": 888001,
                "type": 1,
                "child_user_id": uid,
            },
        )

        # 3. 排课 (产生 A/B 块训练项)
        schedule = client.post(
            f"/api/training/schedule?user_id={uid}",
            json={"planned_minutes": 45},
        )
        assert schedule.status_code == 200
        items = schedule.json()["items"]
        assert len(items) >= 2, f"排课后应至少有2个训练项，实际: {len(items)}"

        plan_id = client.get(f"/api/training/today?user_id={uid}").json()["plan_id"]
        return uid, items, plan_id

    def test_full_ab_checkin_flow(self, client, mock_doubao):
        """全链路: A打卡(一次完成所有A项) → B打卡(一次完成所有B项) → 计划完成

        关键行为: 后端收到一个 block 中任意 item 的打卡后，同 block 内所有 pending 项
        自动标记为 done。前端一次提交即可完成整个 block，无需逐个 item 打卡。
        """
        uid, items, plan_id = self._setup_user_with_schedule(client)

        a_items = [i for i in items if i.get("block") == "A"]
        b_items = [i for i in items if i.get("block") == "B"]
        assert len(a_items) >= 1, f"应有至少1个A块项，实际: {len(a_items)}"
        assert len(b_items) >= 1, f"应有至少1个B块项，实际: {len(b_items)}"

        # --- A 打卡一次 → 同 block 所有 A 项联动完成 ---
        res = client.post(
            f"/api/training/checkin?user_id={uid}",
            json={
                "plan_id": plan_id,
                "item_id": a_items[0]["id"],
                "attitude_pct": 80,
                "cards": [{"name": "影像追忆", "time": "1"}],
            },
        )
        assert res.status_code == 200, f"A块打卡失败: {res.text}"
        assert res.json()["plan_status"] == "pending", "B块未完成，plan 仍为 pending"

        # 验证 A 项全部 done, B 项全部 pending
        today = client.get(f"/api/training/today?user_id={uid}").json()
        for it in today["items"]:
            if it.get("block") == "A":
                assert it["checkin_status"] == "done", f"A项 {it['id']} 应为 done"
            elif it.get("block") == "B":
                assert it["checkin_status"] == "pending", f"B项 {it['id']} 应为 pending"

        # 验证后续 A 项不再可打（first_pending 已移至 B）
        if len(a_items) > 1:
            res2 = client.post(
                f"/api/training/checkin?user_id={uid}",
                json={
                    "plan_id": plan_id,
                    "item_id": a_items[1]["id"],
                    "attitude_pct": 80,
                    "cards": [{"name": "影像追忆", "time": "2"}],
                },
            )
            assert res2.status_code == 400, "已完成的A项再打卡应被拒绝"
            assert "请按顺序完成训练项" in res2.text

        # --- B 打卡一次 → 同 block 所有 B 项联动完成 ---
        res = client.post(
            f"/api/training/checkin?user_id={uid}",
            json={
                "plan_id": plan_id,
                "item_id": b_items[0]["id"],
                "attitude_pct": 80,
                "cards": [{"name": "极速运算", "time": "5", "tag": "口算", "count": "10", "accuracy": "95"}],
            },
        )
        assert res.status_code == 200, f"B块打卡失败: {res.text}"
        assert res.json()["plan_status"] == "completed"

        # --- 验证全部完成 ---
        progress = client.get(f"/api/training/progress?user_id={uid}").json()
        assert progress["today_completed"] is True
        assert progress["total_checkins"] == 2, f"应为2条打卡记录(A+B各一)，实际: {progress['total_checkins']}"

    def test_b_before_a_rejected(self, client, mock_doubao):
        """越序打卡: 未完成 A 时直接打 B 应被拒绝"""
        uid, items, plan_id = self._setup_user_with_schedule(client)

        b_items = [i for i in items if i.get("block") == "B"]
        assert len(b_items) >= 1

        # 直接尝试打第一个 B 项 (跳过 A)
        res = client.post(
            f"/api/training/checkin?user_id={uid}",
            json={
                "plan_id": plan_id,
                "item_id": b_items[0]["id"],
                "attitude_pct": 80,
                "cards": [{"name": "极速运算", "time": "5"}],
            },
        )
        assert res.status_code == 400
        assert "请按顺序完成训练项" in res.text

    def test_wrong_item_id_for_b_rejected(self, client, mock_doubao):
        """Bug 回归: A 完成后用 items[0].id (A项ID) 打 B 应被拒绝

        对应前端 bug: submitFormB 曾写死 todayPlan.value.items[0].id，
        在 A 完成后 items[0] 仍是已完成的 A 项 (sort_order=1)，后端应拒绝。
        """
        uid, items, plan_id = self._setup_user_with_schedule(client)

        a_items = [i for i in items if i.get("block") == "A"]

        # 完成 A (一次打卡搞定所有 A 项)
        res_a = client.post(
            f"/api/training/checkin?user_id={uid}",
            json={
                "plan_id": plan_id,
                "item_id": a_items[0]["id"],
                "attitude_pct": 80,
                "cards": [{"name": "影像追忆", "time": "1"}],
            },
        )
        assert res_a.status_code == 200

        # 模拟前端 bug: 用 items[0].id (sort_order=1 的已完成 A 项) 来打 B
        res = client.post(
            f"/api/training/checkin?user_id={uid}",
            json={
                "plan_id": plan_id,
                "item_id": items[0]["id"],  # <-- BUG: 这是已完成的 A 项
                "attitude_pct": 80,
                "cards": [{"name": "极速运算", "time": "5"}],
            },
        )
        assert res.status_code == 400, (
            f"用已完成的A项ID打B应被拒绝，实际状态码: {res.status_code}"
        )
        assert "请按顺序完成训练项" in res.text, (
            f"错误消息应为'请按顺序完成训练项'，实际: {res.text}"
        )

    def test_complete_without_item_id(self, client, mock_doubao):
        """不传 item_id 时系统自动取第一个 pending 项，并联动完成同 block 全部项"""
        uid, items, plan_id = self._setup_user_with_schedule(client)

        # 第一次不传 item_id → 自动选第一个 pending (A1) → 所有 A 项联动完成
        res = client.post(
            f"/api/training/checkin?user_id={uid}",
            json={
                "plan_id": plan_id,
                "attitude_pct": 72,
                "cards": [{"name": "影像追忆", "time": "2"}],
            },
        )
        assert res.status_code == 200
        assert res.json()["plan_status"] == "pending"

        # 第二次不传 item_id → 自动选第一个 pending (现在是 B1) → 所有 B 项联动完成
        res = client.post(
            f"/api/training/checkin?user_id={uid}",
            json={
                "plan_id": plan_id,
                "attitude_pct": 75,
                "cards": [{"name": "极速运算", "time": "1"}],
            },
        )
        assert res.status_code == 200
        assert res.json()["plan_status"] == "completed"

        # 全部完成，共 2 条打卡记录
        progress = client.get(f"/api/training/progress?user_id={uid}").json()
        assert progress["today_completed"] is True
        assert progress["total_checkins"] == 2

    def test_correct_item_id_for_b_checkin(self, client, mock_doubao):
        """验证修复: A 完成后，B 打卡传 B 项 ID 可以成功"""
        uid, items, plan_id = self._setup_user_with_schedule(client)

        a_items = [i for i in items if i.get("block") == "A"]
        b_items = [i for i in items if i.get("block") == "B"]

        # 完成 A
        client.post(
            f"/api/training/checkin?user_id={uid}",
            json={
                "plan_id": plan_id,
                "item_id": a_items[0]["id"],
                "attitude_pct": 80,
                "cards": [{"name": "影像追忆", "time": "1"}],
            },
        )

        # B 打卡传正确的 B 项 ID → 应该成功
        res = client.post(
            f"/api/training/checkin?user_id={uid}",
            json={
                "plan_id": plan_id,
                "item_id": b_items[0]["id"],  # ← 正确: 第一个 B 项
                "attitude_pct": 80,
                "cards": [{"name": "极速运算", "time": "5"}],
            },
        )
        assert res.status_code == 200, (
            f"B打卡传正确B项ID应成功，实际: {res.status_code} {res.text}"
        )
        assert res.json()["plan_status"] in ("pending", "completed")


class TestResources:
    def test_list_resources(self, client, db_session):
        res = client.get("/api/resources/list?talent_code=1")
        assert res.status_code == 200
        assert res.json()["total"] >= 8
