"""引导页：有 KB 时策略让步 + 练法回答强化。"""

from unittest.mock import patch

import pytest

from app.agents.guide.context import GuideContext
from app.agents.guide.long_term import LongTermSummary
from app.agents.guide.strategy import resolve_strategy, strategy_to_prompt_block


def test_strategy_skips_ready_to_train_defer_when_kb():
    ctx = GuideContext(
        1,
        "2026-08-27",
        talent="赢者",
        situation="ready_to_train",
        next_action="train",
        has_assessment=True,
    )
    s = resolve_strategy(ctx, LongTermSummary(), kb_context=True)
    block = strategy_to_prompt_block(s)
    assert "talent:赢者" in s["keys"]
    assert "可开练" not in block
    assert "知识库" in block
    assert "闯关" not in block or "勿用空泛" in block


def test_strategy_keeps_ready_to_train_without_kb():
    ctx = GuideContext(
        1,
        "2026-08-27",
        talent="赢者",
        situation="ready_to_train",
        next_action="train",
    )
    s = resolve_strategy(ctx, LongTermSummary(), kb_context=False)
    assert "situation:ready_to_train" in s["keys"]


@pytest.mark.asyncio
async def test_gather_rag_uses_enriched_query(monkeypatch):
    monkeypatch.setenv("GUIDE_RAG_ENABLED", "1")

    captured: dict = {}

    async def _fake_query(query, **kwargs):
        captured["query"] = query
        from app.services.bailian.models import RagNode, RagResult

        return RagResult(
            nodes=[RagNode(text="扫读抓关键词", doc_name="练法")],
            mode="retrieve",
            query=query,
        )

    with patch("app.services.bailian.guide_rag_query", side_effect=_fake_query):
        from app.agents.guide.runner import _gather_rag

        block, sources = await _gather_rag("超脑阅读具体怎么练习")

    assert "训练方法" in captured["query"]
    assert "超脑阅读" in captured["query"]
    assert block
    assert sources


def test_build_prompt_includes_practice_hint(db_session, monkeypatch):
    monkeypatch.setenv("GUIDE_STRATEGY_ENABLED", "1")
    from app.agents.guide.runner import build_chat_system_prompt
    from app.services.auth_service import register_child

    user = register_child(db_session, parent_phone="1390000kb01", nickname="KB童")
    rag = "[1] (训练手册)\n先从扫读开始，逐行加速再抓关键词。"
    prompt = build_chat_system_prompt(
        db_session,
        user.id,
        message="超脑阅读具体怎么练习",
        rag_block=rag,
    )
    assert "知识库参考" in prompt
    assert "具体可操作方法" in prompt or "可操作" in prompt
    assert "禁止只用天赋策略" in prompt or "套话" in prompt
    assert "可开练" not in prompt or "知识库" in prompt
