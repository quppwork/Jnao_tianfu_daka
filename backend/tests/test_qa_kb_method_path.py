"""学科答疑 — METHOD 知识库路径注入 runner（mock 百炼）。"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.harness.types import ToolResult


def _kb_result(answer: str, *, sources=None) -> ToolResult:
    return ToolResult(
        ok=True,
        name="retrieve_qa_kb",
        data={
            "ok": True,
            "rag_used": True,
            "rag_context": answer,
            "rag_sources": list(sources or ["练法手册"]),
            "rag_source": "bailian_method",
            "rag_kind": "method",
        },
    )


@pytest.mark.asyncio
async def test_fetch_method_bundle_sets_kind():
    from app.agents.qa.runner import _fetch_qa_rag_bundle

    with patch(
        "app.harness.runtime.call_tool",
        new=AsyncMock(return_value=_kb_result("先系统训练再专题")),
    ):
        bundle = await _fetch_qa_rag_bundle(
            "数学怎么学",
            child_user_id=1,
            subject="数学",
            has_image=False,
            use_rag=None,
        )
    assert bundle["rag_used"] is True
    assert bundle["rag_kind"] == "method"
    assert bundle["rag_source"] == "bailian_method"
    assert "系统训练" in bundle["rag_context"]


@pytest.mark.asyncio
async def test_fetch_homework_skips_kb():
    from app.agents.qa.runner import _fetch_qa_rag_bundle

    with patch(
        "app.harness.runtime.call_tool",
        new=AsyncMock(return_value=_kb_result("不应调用")),
    ) as tool_mock:
        bundle = await _fetch_qa_rag_bundle(
            "这道应用题怎么解",
            child_user_id=1,
            subject="数学",
            has_image=False,
            use_rag=None,
        )
    assert bundle["rag_used"] is False
    tool_mock.assert_not_called()


def test_chat_method_kb_injected_into_prompt(client: TestClient, child_with_assessment, mock_doubao):
    uid = child_with_assessment
    captured: dict = {}

    async def fake_turn(profile, user_message, **kwargs):
        captured["system"] = kwargs.get("system_override")
        return {"reply": "按系统训练先打基础。", "tools_used": [], "rag_used": True}

    with patch(
        "app.harness.runtime.call_tool",
        new=AsyncMock(
            return_value=_kb_result("知识库：系统训练优于单点刷题", sources=["天赋文档"])
        ),
    ), patch(
        "app.runtime.run_turn",
        new=fake_turn,
    ):
        res = client.post(
            f"/api/qa/chat?user_id={uid}",
            json={"message": "数学怎么学", "subject": "数学"},
        )
    assert res.status_code == 200
    assert "平台特殊训练方法" in captured["system"]
    assert "系统训练优于单点刷题" in captured["system"]
