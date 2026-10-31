"""Agent 工具 knowledge_qa：原样返回百炼知识问答 reply。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.harness.registry import reset_registry_for_tests
from app.harness.tools import knowledge_qa as tool


@pytest.fixture(autouse=True)
def _iso():
    reset_registry_for_tests()
    yield
    reset_registry_for_tests()


@pytest.mark.asyncio
async def test_knowledge_qa_returns_reply_as_is():
    fake = SimpleNamespace(
        reply="五者是一套诊断体系。",
        aid="aid-9eca891478184a39a7e0d37419919ae9",
        request_id="rid-1",
        retrieved_docs=[],
        stages=["generating"],
    )
    with patch(
        "app.services.bailian.knowledge_chat.knowledge_chat_sync", return_value=fake
    ), patch(
        "app.services.bailian.config.load_bailian_config",
        return_value=SimpleNamespace(
            workspace_id="ws", dashscope_api_key="sk", dense_top_k=6
        ),
    ), patch("app.core.async_workers.run_sync", new=AsyncMock(return_value=fake)):
        out = await tool.knowledge_qa({"query": "五者是什么"})
    assert out["ok"] is True
    assert out["reply"] == "五者是一套诊断体系。"
    assert out["aid"] == "aid-9eca891478184a39a7e0d37419919ae9"


@pytest.mark.asyncio
async def test_knowledge_qa_empty_is_not_ok():
    with patch(
        "app.core.async_workers.run_sync",
        new=AsyncMock(return_value=SimpleNamespace(reply="", request_id=None)),
    ), patch(
        "app.services.bailian.config.load_bailian_config",
        return_value=SimpleNamespace(
            workspace_id="ws", dashscope_api_key="sk", dense_top_k=6
        ),
    ):
        out = await tool.knowledge_qa({"query": "随便"})
    assert out["ok"] is False
    assert out["error_kind"] == "empty"
