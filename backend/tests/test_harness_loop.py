"""统一 Agent loop：假模型驱动，不打真实 LLM。"""

from __future__ import annotations

from typing import Any

import pytest

from app.harness.checkpoint import reset_all
from app.harness.loop import run_agent
from app.harness.registry import reset_registry_for_tests


@pytest.fixture(autouse=True)
def _iso(monkeypatch):
    monkeypatch.setenv("HARNESS_SANDBOX", "local")
    reset_registry_for_tests()
    reset_all()
    yield
    reset_all()
    reset_registry_for_tests()


class QueueModel:
    def __init__(self, replies: list[dict[str, Any]]):
        self.replies = list(replies)

    async def complete(self, messages, tools):
        if not self.replies:
            return {"role": "assistant", "content": "done"}
        return self.replies.pop(0)


@pytest.mark.asyncio
async def test_loop_completes_without_tools():
    model = QueueModel([{"role": "assistant", "content": "你好，我是大宇"}])
    state = await run_agent(
        profile="consult",
        user_message="在吗",
        thread_id="t-plain",
        model=model,
        max_steps=3,
    )
    assert state.status == "completed"
    assert state.reply == "你好，我是大宇"


@pytest.mark.asyncio
async def test_loop_runs_readonly_tool_then_answers():
    fake = type("R", (), {})()
    fake.rag_block = "超脑阅读每天练"
    fake.nodes = []
    fake.mode = "retrieve"

    from unittest.mock import AsyncMock, patch

    model = QueueModel(
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {
                            "name": "retrieve_kb",
                            "arguments": '{"query":"超脑阅读"}',
                        },
                    }
                ],
            },
            {"role": "assistant", "content": "根据知识库：每天练。"},
        ]
    )
    with patch(
        "app.services.bailian.guide_rag_query",
        new=AsyncMock(return_value=fake),
    ):
        state = await run_agent(
            profile="consult",
            user_message="怎么练超脑阅读",
            thread_id="t-rag",
            model=model,
            max_steps=4,
        )
    assert state.status == "completed"
    assert "每天练" in state.reply
    assert any(t.get("name") == "retrieve_kb" for t in state.tool_trace)


@pytest.mark.asyncio
async def test_loop_interrupts_on_confirm_then_resume():
    model = QueueModel(
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "w1",
                        "function": {
                            "name": "create_course",
                            "arguments": '{"title":"试点课"}',
                        },
                    }
                ],
            },
            {"role": "assistant", "content": "已记录你的确认，课程写入尚未接 LMS。"},
        ]
    )
    state = await run_agent(
        profile="teacher",
        user_message="建一门课",
        thread_id="t-hitl",
        model=model,
        max_steps=5,
    )
    assert state.status == "awaiting_approval"
    assert state.pending_approvals
    token = state.pending_approvals[0].confirm_token
    resumed = await run_agent(
        profile="teacher",
        user_message="",
        thread_id="t-hitl",
        model=model,
        resume_tokens=[token],
        max_steps=5,
    )
    assert resumed.status == "completed"
    assert "LMS" in resumed.reply or "确认" in resumed.reply or resumed.reply


class RetryThenOk:
    def __init__(self):
        self.n = 0

    async def complete(self, messages, tools):
        self.n += 1
        if self.n == 1:
            raise RuntimeError("boom")
        return {"role": "assistant", "content": "重试后回复"}


@pytest.mark.asyncio
async def test_loop_retries_llm_once():
    model = RetryThenOk()
    state = await run_agent(
        profile="consult",
        user_message="hi",
        thread_id="t-retry",
        model=model,
        max_steps=2,
        allow_tools=False,
    )
    assert model.n == 2
    assert state.reply == "重试后回复"
    assert state.metadata.get("llm_calls") == 1


@pytest.mark.asyncio
async def test_loop_rejects_oversized_message():
    from app.harness.policy import MAX_USER_CHARS

    state = await run_agent(
        profile="consult",
        user_message="x" * (MAX_USER_CHARS + 1),
        thread_id="t-long",
        model=QueueModel([{"role": "assistant", "content": "不该到这"}]),
        max_steps=1,
    )
    assert state.status == "failed"
    assert "缩短" in state.reply


@pytest.mark.asyncio
async def test_iter_agent_yields_tokens():
    from app.harness.loop import iter_agent

    model = QueueModel([{"role": "assistant", "content": "流式一段"}])
    kinds = []
    reply = ""
    async for kind, payload in iter_agent(
        profile="consult",
        user_message="在吗",
        thread_id="t-stream",
        model=model,
        max_steps=2,
        allow_tools=False,
        fresh=True,
    ):
        kinds.append(kind)
        if kind == "token":
            reply += str(payload)
    assert "token" in kinds
    assert kinds[-1] == "done"
    assert "流式一段" in reply


@pytest.mark.asyncio
async def test_iter_agent_chunks_when_tools_enabled():
    """allow_tools=True 时走 complete，最终正文应拆成多段 token，避免整段弹出。"""
    from app.harness.loop import iter_agent

    long_reply = "第一步先读题。" * 8 + "第二步再回原文定位关键词。" * 6
    model = QueueModel([{"role": "assistant", "content": long_reply}])
    token_parts: list[str] = []
    async for kind, payload in iter_agent(
        profile="qa",
        user_message="这道阅读怎么做",
        thread_id="t-qa-stream",
        model=model,
        max_steps=2,
        allow_tools=True,
        fresh=True,
    ):
        if kind == "token":
            token_parts.append(str(payload))
    assert len(token_parts) >= 3
    assert "".join(token_parts) == long_reply


@pytest.mark.asyncio
async def test_loop_compacts_long_history():
    hist = [{"role": "user", "content": f"旧{i}"} for i in range(40)]
    seen = []

    class Spy(QueueModel):
        async def complete(self, messages, tools):
            seen.append(len(messages))
            return await super().complete(messages, tools)

    model = Spy([{"role": "assistant", "content": "ok"}])
    await run_agent(
        profile="consult",
        user_message="新问",
        history=hist,
        thread_id="t-fold",
        model=model,
        max_steps=2,
        allow_tools=False,
        fresh=True,
    )
    assert seen
    assert seen[0] <= 22

@pytest.mark.asyncio
async def test_max_tool_rounds_forces_answer_without_tools():
    """工具轮用完即撤 tools：模型必须直接出话，不再靠 max_steps 兜底。"""
    from unittest.mock import AsyncMock, patch

    class ToolHungry:
        def __init__(self):
            self.seen: list[list] = []

        async def complete(self, messages, tools):
            self.seen.append(list(tools or []))
            if tools:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "c1",
                            "function": {
                                "name": "retrieve_kb",
                                "arguments": '{"query":"超脑阅读"}',
                            },
                        }
                    ],
                }
            return {"role": "assistant", "content": "按已查到的切片作答。"}

    fake = type("R", (), {})()
    fake.rag_block = "超脑阅读每天练"
    fake.nodes = []
    fake.mode = "retrieve"

    model = ToolHungry()
    with patch("app.services.bailian.guide_rag_query", new=AsyncMock(return_value=fake)):
        state = await run_agent(
            profile="consult",
            user_message="怎么练超脑阅读",
            thread_id="t-rounds",
            model=model,
            max_steps=5,
            max_tool_rounds=1,
        )
    assert state.status == "completed"
    assert state.reply == "按已查到的切片作答。"
    assert len(model.seen) == 2
    assert model.seen[1] == []
    assert state.metadata.get("tool_rounds") == 1


@pytest.mark.asyncio
async def test_tool_citations_collected_into_metadata():
    from app.harness.registry import register_tool
    from app.harness.types import ToolSpec

    async def _handler(args):
        return {"ok": True, "citations": ["名人堂", "天赋剧场"]}

    register_tool(
        ToolSpec(
            name="fake_cite",
            description="测试引用",
            input_schema={"type": "object", "properties": {}, "additionalProperties": True},
            handler=_handler,
            profiles=("consult",),
        )
    )

    class CiteModel:
        def __init__(self):
            self.n = 0

        async def complete(self, messages, tools):
            self.n += 1
            if self.n == 1:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"id": "c1", "function": {"name": "fake_cite", "arguments": "{}"}}
                    ],
                }
            return {"role": "assistant", "content": "引用已带上。"}

    state = await run_agent(
        profile="consult",
        user_message="看榜样的故事",
        thread_id="t-cite",
        model=CiteModel(),
        max_steps=3,
    )
    assert state.status == "completed"
    assert state.metadata.get("citations") == ["名人堂", "天赋剧场"]
