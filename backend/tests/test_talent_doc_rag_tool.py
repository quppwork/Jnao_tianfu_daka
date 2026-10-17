"""talent_doc_retrieve 工具契约与空命中。"""

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
