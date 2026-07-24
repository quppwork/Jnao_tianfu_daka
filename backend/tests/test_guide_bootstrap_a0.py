# -*- coding: utf-8 -*-
"""首页引导 A0：情境判定 + bootstrap 开场"""

import pytest

from app.agents.guide.context import GuideContext, TodayPlanSnapshot
from app.agents.guide.memory import clear_bootstrap_cache, get_cached_welcome, set_cached_welcome
from app.agents.guide.situations import resolve_situation, template_welcome
from app.db.models import ChildUser


class TestResolveSituation:
    def test_need_assessment(self):
        ctx = GuideContext(1, "2026-07-23", has_assessment=False)
        assert resolve_situation(ctx) == ("need_assessment", "talent")

    def test_ready_to_train(self):
        ctx = GuideContext(1, "2026-07-23", has_assessment=True, days_since_last_checkin=1)
        assert resolve_situation(ctx) == ("ready_to_train", "train")

    def test_sparse_return(self):
        ctx = GuideContext(1, "2026-07-23", has_assessment=True, days_since_last_checkin=5)
        assert resolve_situation(ctx) == ("sparse_return", "train")

    def test_training_in_progress(self):
        ctx = GuideContext(1, "2026-07-23", has_assessment=True)
        ctx.today = TodayPlanSnapshot(
            exists=True, item_count=2, done_count=0, has_started=True, status="pending"
        )
        assert resolve_situation(ctx) == ("training_in_progress", "train")

    def test_training_done(self):
        ctx = GuideContext(1, "2026-07-23", has_assessment=True)
        ctx.today = TodayPlanSnapshot(
            exists=True, item_count=2, done_count=2, has_started=True, status="completed"
        )
        assert resolve_situation(ctx) == ("training_done", "qa")


class TestTemplateWelcome:
    def test_includes_nickname(self):
        text = template_welcome("ready_to_train", nickname="小明")
        assert text.startswith("小明，")


@pytest.mark.asyncio
async def test_bootstrap_need_assessment(db_session, client):
    from app.services.auth_service import register_child

    clear_bootstrap_cache()
    user = register_child(db_session, parent_phone="1390000a001", nickname="引导未测")
    # 无测评 → need_assessment
    from app.services import guide_service

    result = await guide_service.bootstrap(db_session, user.id, force=True, use_llm=False)
    assert result["situation"] == "need_assessment"
    assert result["next_action"] == "talent"
    assert result["welcome"]
    assert result["source"] == "template"

    # 同日二次 → cache
    again = await guide_service.bootstrap(db_session, user.id, force=False, use_llm=False)
    assert again["source"] == "cache"
    assert again["welcome"] == result["welcome"]


@pytest.mark.asyncio
async def test_bootstrap_api(client, user_ready_for_training):
    clear_bootstrap_cache()
    uid = user_ready_for_training
    res = client.post(
        "/api/guide/bootstrap",
        json={"force": True, "use_llm": False},
        headers={"X-Child-User-Id": str(uid)},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["situation"] in {
        "ready_to_train",
        "sparse_return",
        "training_in_progress",
        "training_done",
        "need_assessment",
    }
    assert data["next_action"] in {"talent", "train", "qa", "growth"}
    assert data["welcome"]
