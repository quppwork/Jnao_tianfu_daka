"""快速发烟测试 — 覆盖 6 条核心链路，< 10 秒。

用法:
    python -m pytest tests/smoke_test.py -v --tb=short

链路:
    1. 健康检查     — 服务存活
    2. 用户体系     — 注册 + 登录 + 个人信息
    3. 天赋测评     — 提交测评，验证 child_user_id 落库
    4. 训练入口     — 无测评→403 / 有测评→200 + 窗口
    5. 打卡流程     — 今日方案 → 逐项打卡 → 完成
    6. 成长+引导    — 徽章/时间线/分享 + AI 引导对话
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("TIANFU_RAG_MOCK", "1")

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_user, get_child_user_id, get_db
from app.db.base import Base
from app.db.session import get_session_factory, init_db
from app.services.catalog_import import import_all_xet_catalogs


@pytest.fixture
def db_session() -> Session:
    init_db()
    session = get_session_factory()()
    import_all_xet_catalogs(session, replace=True)
    yield session
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(delete(table))
    session.commit()
    session.close()


def _make_client(db_session):
    with (
        patch("app.api.talent.jnao_submit", new_callable=AsyncMock) as m_sub,
        patch("app.api.talent.jnao_get_report", new_callable=AsyncMock) as m_rep,
        patch("app.services.doubao_client.chat_completion", new_callable=AsyncMock, return_value="【测试】OK"),
        patch("app.services.guide_service.chat_completion", new_callable=AsyncMock, return_value="【测试】OK"),
        patch("app.api.chat.chat_completion", new_callable=AsyncMock, return_value="【测试】OK"),
        patch("app.services.qa_service.chat_completion", new_callable=AsyncMock, return_value="【测试】OK"),
        patch("app.services.qa_service.vision_chat_completion", new_callable=AsyncMock, return_value="【测试】识图"),
        patch("app.services.doubao_client.vision_chat_completion", new_callable=AsyncMock, return_value="【测试】识图"),
        patch("app.services.training_plan_generator.chat_completion", new_callable=AsyncMock, return_value="【测试】OK"),
        patch("app.services.doubao_client.is_configured", return_value=True),
        patch("app.api.chat.is_configured", return_value=True),
    ):
        m_sub.return_value = "test-record-123"
        m_rep.return_value = {
            "id": 123, "uid": 999888, "type": 1,
            "talent": "学者", "check_talent": "学者",
            "create_time": "2026-06-18", "results": {},
            "property": "[]", "AttributeJs": "{}", "StateIcon": "",
        }

        from main import app

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_authenticated_user] = get_child_user_id
        with TestClient(app) as tc:
            yield tc
        app.dependency_overrides.clear()


@pytest.fixture
def client(db_session):
    yield from _make_client(db_session)


def _register(client, phone="13900000001", nickname="发烟童"):
    return client.post("/api/auth/register", json={"parent_phone": phone, "nickname": nickname})


def _assess(client, uid):
    """提交天赋测评 — child_user_id 必须在 body 中才能正确落库"""
    return client.post(
        "/api/talent/report",
        json={"answer": "1" * 35, "uid": 888001, "type": 1, "child_user_id": uid},
    )


class TestSmoke:
    """全线发烟 — 每 test 独立（fixture 隔离 DB，SQLite 内存库）"""

    # ══ 1. 健康检查 ══
    def test_01_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    # ══ 2. 用户体系 ══
    def test_02_register(self, client):
        r = _register(client)
        assert r.status_code == 200
        body = r.json()
        assert body["child_user_id"] > 0
        assert body["nickname"] == "发烟童"

    def test_03_login(self, client):
        body = {"parent_phone": "13900000002", "nickname": "登录童"}
        client.post("/api/auth/register", json=body)
        r = client.post("/api/auth/login", json=body)
        assert r.status_code == 200
        assert r.json()["nickname"] == "登录童"

    def test_04_profile(self, client):
        reg = _register(client)
        uid = reg.json()["child_user_id"]
        r = client.get(f"/api/user/profile?user_id={uid}")
        assert r.status_code == 200
        assert r.json()["parent_phone"] == "13900000001"

    # ══ 3. 天赋测评 ══
    def test_05_submit_assessment(self, client):
        reg = _register(client)
        uid = reg.json()["child_user_id"]
        r = _assess(client, uid)
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 1
        assert body["data"]["talent"] == "学者"
        assert body["assessment_id"] is not None

    # ══ 4. 训练入口 ══
    def test_06_today_requires_assessment(self, client):
        """无测评 → 403"""
        reg = _register(client)
        uid = reg.json()["child_user_id"]
        r = client.get(f"/api/training/today?user_id={uid}")
        assert r.status_code == 403

    def test_07_today_with_assessment(self, client):
        """有测评 + child_user_id 落库 → 200"""
        reg = _register(client)
        uid = reg.json()["child_user_id"]
        _assess(client, uid)
        r = client.get(f"/api/training/today?user_id={uid}")
        assert r.status_code == 200
        body = r.json()
        assert "plan_id" in body

    def test_08_training_window(self, client):
        reg = _register(client)
        uid = reg.json()["child_user_id"]
        _assess(client, uid)
        r = client.post(f"/api/training/window?user_id={uid}", json={
            "start_time": "08:00", "end_time": "09:00",
        })
        assert r.status_code == 200
        r2 = client.get(f"/api/training/window?user_id={uid}")
        assert r2.status_code == 200

    # ══ 5. 打卡流程 ══
    def test_09_checkin_flow(self, client):
        reg = _register(client)
        uid = reg.json()["child_user_id"]
        _assess(client, uid)

        today = client.get(f"/api/training/today?user_id={uid}")
        assert today.status_code == 200
        plan = today.json()

        # A 项打卡
        for item in plan.get("items", []):
            if item.get("item_type") != "a_lesson":
                continue
            r = client.post(f"/api/training/checkin?user_id={uid}", json={
                "plan_id": plan["id"],
                "item_id": item["id"],
                "action": "complete",
            })
            assert r.status_code == 200, f"A打卡失败: {r.text}"

        # B 项打卡
        for item in plan.get("items", []):
            if item.get("item_type") != "b_lesson":
                continue
            r = client.post(f"/api/training/checkin?user_id={uid}", json={
                "plan_id": plan["id"],
                "item_id": item["id"],
                "action": "complete",
            })
            assert r.status_code == 200, f"B打卡失败: {r.text}"

    def test_10_checkin_today(self, client):
        reg = _register(client)
        uid = reg.json()["child_user_id"]
        _assess(client, uid)
        r = client.get(f"/api/training/checkin/today?user_id={uid}")
        assert r.status_code == 200

    # ══ 6. 成长 + 引导 ══
    def test_11_badges(self, client):
        reg = _register(client)
        uid = reg.json()["child_user_id"]
        _assess(client, uid)
        r = client.get(f"/api/growth/badges?user_id={uid}")
        assert r.status_code == 200

    def test_12_timeline(self, client):
        reg = _register(client)
        uid = reg.json()["child_user_id"]
        _assess(client, uid)
        r = client.get(f"/api/growth/timeline?user_id={uid}")
        assert r.status_code == 200

    def test_13_share_text(self, client):
        reg = _register(client)
        uid = reg.json()["child_user_id"]
        _assess(client, uid)
        r = client.get(f"/api/growth/share?user_id={uid}")
        assert r.status_code == 200
        assert "成长" in r.json()["title"]

    def test_14_guide_chat(self, client):
        reg = _register(client)
        uid = reg.json()["child_user_id"]
        r = client.post(f"/api/guide/chat?user_id={uid}", json={"message": "你好"})
        assert r.status_code == 200
        assert "reply" in r.json()

    def test_15_guide_session(self, client):
        reg = _register(client)
        uid = reg.json()["child_user_id"]
        client.post(f"/api/guide/chat?user_id={uid}", json={"message": "你好"})
        r = client.get(f"/api/guide/session?user_id={uid}")
        assert r.status_code == 200
