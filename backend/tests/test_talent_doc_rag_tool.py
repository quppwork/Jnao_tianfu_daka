"""talent_doc_retrieve 工具契约与空命中。"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.harness.tools import talent_doc_rag as tool
from app.services.bailian.models import RagNode, RagResult


@pytest.mark.asyncio
async def test_contract_blocks_extra_args():
    out = await tool.talent_doc_retrieve({"query": "学者", "evil": 1})
    assert out["ok"] is False
    assert out["error_kind"] == "contract_input"


@pytest.mark.asyncio
async def test_empty_hits():
    empty = RagResult(nodes=[], mode="retrieve", query="q")
    with patch("app.services.bailian.retrieve.retrieve_sync", return_value=empty):
        out = await tool.talent_doc_retrieve({"query": "闲聊天气"})
    assert out["ok"] is False
    assert out["error_kind"] == "empty"
    assert out["source_key"] == "talent_doc"
    assert out["index_id"] == "x1micrdmjq"


@pytest.mark.asyncio
async def test_success_hits():
    hit = RagResult(
        nodes=[RagNode(text="学者靠阅读推进", score=0.9, doc_name="五者")],
        mode="retrieve",
        query="q",
        request_id="rid-1",
    )
    with patch("app.services.bailian.retrieve.retrieve_sync", return_value=hit):
        out = await tool.talent_doc_retrieve({"query": "学者怎么练"})
    assert out["ok"] is True
    assert out["hit_count"] == 1
    assert out["hits"][0]["text"].startswith("学者")
    assert out["request_id"] == "rid-1"


@pytest.mark.asyncio
async def test_runtime_exception():
    with patch(
        "app.services.bailian.retrieve.retrieve_sync",
        side_effect=RuntimeError("boom"),
    ), patch("app.harness.tools.talent_doc_rag.get_cost_recorder") as cost:
        cost.return_value = MagicMock()
        out = await tool.talent_doc_retrieve({"query": "学者"})
    assert out["ok"] is False
    assert out["error_kind"] == "runtime"

@pytest.mark.asyncio
async def test_citations_from_hit_metadata():
    hit = RagResult(
        nodes=[
            RagNode(text="执行力偏弱先做目标拆解", score=0.8, title="五维能量星图"),
            RagNode(text="榜样故事", score=0.7, doc_name="名人堂"),
        ],
        mode="retrieve",
        query="执行力",
    )
    with patch("app.services.bailian.retrieve.retrieve_sync", return_value=hit):
        out = await tool.talent_doc_retrieve({"query": "执行力怎么练"})
    assert out["ok"] is True
    assert out["citations"] == ["五维能量星图", "名人堂"]


@pytest.mark.asyncio
async def test_retrieve_timeout_returns_timeout_kind():
    async def _timeout(*_a, **_k):
        raise asyncio.TimeoutError()

    with patch("app.services.bailian.retrieve.retrieve", new=_timeout), patch(
        "app.harness.tools.talent_doc_rag.get_cost_recorder"
    ) as cost:
        cost.return_value = MagicMock()
        out = await tool.talent_doc_retrieve({"query": "学者"})
    assert out["ok"] is False
    assert out["error_kind"] == "timeout"


@pytest.mark.asyncio
async def test_success_is_cached_and_failure_is_not():
    tool._CACHE.clear()
    hit = RagResult(
        nodes=[RagNode(text="学者靠阅读推进", score=0.9, doc_name="五者")],
        mode="retrieve",
        query="q",
    )
    with patch(
        "app.services.bailian.retrieve.retrieve_sync", return_value=hit
    ) as sdk:
        first = await tool.talent_doc_retrieve({"query": "缓存问题"})
        second = await tool.talent_doc_retrieve({"query": "缓存问题"})
    assert first["ok"] is True and second == first
    assert sdk.call_count == 1

    empty = RagResult(nodes=[], mode="retrieve", query="q")
    with patch(
        "app.services.bailian.retrieve.retrieve_sync", return_value=empty
    ) as sdk:
        await tool.talent_doc_retrieve({"query": "无命中问题"})
        await tool.talent_doc_retrieve({"query": "无命中问题"})
    assert sdk.call_count == 2
