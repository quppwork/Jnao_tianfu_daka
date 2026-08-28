"""KB 优先 / 模板兜底 测试。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.guide.context import GuideContext
from app.services.guide_rag_fallback import build_rag_miss_fallback


def test_practice_miss_template_super_brain():
    ctx = GuideContext(1, "2026-08-27", talent="赢者", situation="ready_to_train")
    text = build_rag_miss_fallback("超脑阅读具体怎么练习", ctx)
    assert text
    assert "超脑阅读" in text
    assert "今日训练" in text


def test_practice_miss_template_kai_kou_qiao():
    ctx = GuideContext(1, "2026-08-27")
    text = build_rag_miss_fallback("开口窍怎么练习", ctx)
    assert "开口窍" in text
    assert "今日训练" in text


def test_talent_miss_template():
    text = build_rag_miss_fallback("学者天赋是什么", GuideContext(1, "2026-08-27"))
    assert "天赋" in text


@pytest.mark.asyncio
async def test_rag_miss_uses_template_not_doubao(monkeypatch):
    monkeypatch.setenv("GUIDE_RAG_ENABLED", "1")
    monkeypatch.setenv("BAILIAN_RAG_GENERATE", "0")

    with patch(
        "app.services.bailian.guide_rag_query",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.agents.guide.runner._try_bailian_direct_reply",
        new=AsyncMock(),
    ), patch(
        "app.services.doubao_client.chat_completion",
        new=AsyncMock(),
    ) as doubao, patch(
        "app.agents.guide.runner._prepare_context",
    ) as prep, patch(
        "app.agents.guide.runner._prepare_memory_and_history",
        return_value=([], ""),
    ), patch(
        "app.agents.guide.runner._gather_tools",
        new=AsyncMock(return_value=([], "")),
    ), patch(
        "app.agents.guide.runner._meta_from_ctx",
        return_value={"situation": "ready_to_train", "actions": []},
    ):
        prep.return_value = GuideContext(
            1, "2026-08-27", talent="赢者", situation="ready_to_train", next_action="train"
        )
        from app.agents.guide.runner import run_chat

        result = await run_chat(object(), 1, "开口窍怎么练习")

    doubao.assert_not_called()
    assert result.get("rag_source") == "template_fallback"
    assert "开口窍" in result["reply"]
    assert "赢者" not in result["reply"] or "小目标" not in result["reply"]


def test_kb_primary_prompt_puts_kb_before_strategy(db_session, monkeypatch):
    monkeypatch.setenv("GUIDE_STRATEGY_ENABLED", "1")
    from app.agents.guide.runner import build_kb_primary_system_prompt
    from app.services.auth_service import register_child

    user = register_child(db_session, parent_phone="1390000kb02", nickname="KB2")
    rag = "[1] (训练手册)\n先从扫读开始，逐行加速再抓关键词。"
    prompt = build_kb_primary_system_prompt(
        db_session,
        user.id,
        rag_block=rag,
        message="超脑阅读怎么练",
    )
    kb_pos = prompt.index("知识库参考")
    strat_pos = prompt.find("个性化策略")
    assert kb_pos >= 0
    if strat_pos >= 0:
        assert kb_pos < strat_pos
    assert "优先依据" in prompt
    assert "扫读" in prompt
    assert "平台四大功能" not in prompt  # KB 路径不注入完整长人设
