"""学科答疑 — 百炼多轮检索客户端测试。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.bailian.models import RagNode, RagResult
from app.services.qa_kb_retrieve import qa_method_kb_ready, retrieve_qa_method_kb


@pytest.mark.asyncio
async def test_retrieve_merges_two_rounds(monkeypatch):
    monkeypatch.setenv("QA_METHOD_KB", "1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")
    monkeypatch.setenv("BAILIAN_WORKSPACE_ID", "ws-test")
    monkeypatch.setenv("BAILIAN_INDEX_ID", "idx-doc")
    monkeypatch.setenv("BAILIAN_VIDEO_INDEX_ID", "idx-video")

    from app.services.kb_registry import get_kb_registry

    get_kb_registry.cache_clear()

    calls: list[dict] = []

    async def fake_rag_query(query, *, index_id=None, top_n=None, timeout=20, **kwargs):
        calls.append({"query": query, "index_id": index_id})
        return RagResult(
            nodes=[
                RagNode(
                    text=f"切片:{query[:20]}",
                    score=0.9,
                    doc_name=f"doc-{index_id}",
                    chunk_id=f"{index_id}-1",
                )
            ],
            mode="retrieve",
            query=query,
        )

    with patch(
        "app.services.qa_kb_retrieve.qa_method_kb_ready",
        return_value=True,
    ), patch(
        "app.services.qa_kb_retrieve.rag_query",
        new=fake_rag_query,
    ):
        hit = await retrieve_qa_method_kb("数学怎么学", subject="数学")

    assert hit is not None
    assert hit["rag_source"] == "bailian_method"
    assert hit["answer"]
    assert len(calls) >= 1
    assert all(c["index_id"] for c in calls)
    assert hit["source_keys"] == ["talent_doc"] or set(hit["source_keys"]) == {"talent_doc"}


@pytest.mark.asyncio
async def test_retrieve_returns_none_when_disabled(monkeypatch):
    monkeypatch.setenv("QA_METHOD_KB", "0")
    assert qa_method_kb_ready() is False
    assert await retrieve_qa_method_kb("数学怎么学", subject="数学") is None


@pytest.mark.asyncio
async def test_retrieve_asserts_source_and_query_for_skill(monkeypatch):
    monkeypatch.setenv("QA_METHOD_KB", "1")

    async def fake_rag_query(query, *, index_id=None, top_n=None, timeout=20, **kwargs):
        return RagResult(
            nodes=[RagNode(text="开口窍慢读", score=0.8, doc_name="video", chunk_id="v1")],
            mode="retrieve",
            query=query,
        )

    with patch(
        "app.services.qa_kb_retrieve.qa_method_kb_ready",
        return_value=True,
    ), patch(
        "app.services.qa_kb_retrieve.rag_query",
        new=AsyncMock(side_effect=fake_rag_query),
    ):
        hit = await retrieve_qa_method_kb("开口窍怎么练", subject="语文")

    assert hit is not None
    assert "开口窍" in hit["queries"][0]
    assert "训练方法" in hit["queries"][0]
