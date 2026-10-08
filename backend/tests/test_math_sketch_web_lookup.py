"""math_sketch / web_lookup 工具冒烟 + MCP 目录收口"""

from __future__ import annotations

import pytest

from app.harness.llm_catalog import QA_PROFILE_TOOLS
from app.harness.registry import reset_registry_for_tests
from app.harness.tools import math_sketch as ms


@pytest.fixture(autouse=True)
def _reset_registry():
    reset_registry_for_tests()
    yield
    reset_registry_for_tests()


def test_math_sketch_ellipse_svg():
    out = ms.sketch_ellipse(
        {"a": 4, "b": 3, "points": [[0, 3, "A"], [3, 1.5, "P"]], "caption": "椭圆示意"}
    )
    assert out["ok"] is True
    assert "<svg" in out["svg"]
    assert "jnao-svg" in out["fence"]
    assert "ellipse" in out["svg"]


def test_math_sketch_plot_parabola():
    out = ms.sketch_plot({"expr": "x**2", "x_min": -2, "x_max": 2})
    assert out["ok"] is True
    assert "path" in out["svg"]


@pytest.mark.asyncio
async def test_web_lookup_empty_query():
    from app.harness.tools.web_lookup import web_lookup

    out = await web_lookup({"query": ""})
    assert out["ok"] is False


def test_qa_mcp_catalog_exposes_lookup_and_sketch():
    from app.harness.catalog import catalog_status, tools_for_server
    from app.harness.client import GatewayMCPClient
    from app.harness.openai_tools import openai_tools_for_profile
    from app.harness.llm import PROFILES

    assert "web_lookup" in PROFILES["qa"]["tools"]
    assert "math_sketch" in PROFILES["qa"]["tools"]

    host_names = {t.name for t in tools_for_server("jnao-host", profile="qa")}
    for name in ("web_lookup", "web_search", "math_sketch", "ocr_extract", "retrieve_qa_kb"):
        assert name in host_names, name
    # 引导页打卡工具不应再挂到答疑 profile
    assert "get_today_plan" not in host_names

    openai_names = {t["function"]["name"] for t in openai_tools_for_profile("qa")}
    assert openai_names <= set(QA_PROFILE_TOOLS)
    assert "web_lookup" in openai_names
    assert "math_sketch" in openai_names

    desc = GatewayMCPClient(profile="qa").describe()
    assert "web_lookup" in desc["host_tools"]
    assert "math_sketch" in desc["host_tools"]

    status = catalog_status()
    jnao = next(s for s in status["servers"] if s["name"] == "jnao-host")
    assert "web_lookup" in jnao["description"]
    assert "math_sketch" in jnao["description"]


@pytest.mark.asyncio
async def test_qa_allowlist_blocks_non_qa_tools():
    from app.harness.runtime import call_tool

    # generate_quiz 仍挂在 qa profiles，但不在 QA_PROFILE_TOOLS 白名单
    blocked = await call_tool(
        "generate_quiz", {"material": "1+1"}, profile="qa"
    )
    assert blocked.ok is False
    assert "allowlist" in (blocked.error or "")

    # 引导工具已从 qa profiles 摘掉
    guide = await call_tool("get_today_plan", {}, profile="qa")
    assert guide.ok is False


def test_append_math_sketch_fence():
    from app.harness.agent_state import AgentState
    from app.harness.loop import _append_math_sketch_fence

    state = AgentState(
        thread_id="t1",
        profile="qa",
        messages=[
            {
                "role": "tool",
                "name": "math_sketch",
                "content": (
                    '{"ok": true, "fence": "```jnao-svg\\n<svg/>\\n```"}'
                ),
            }
        ],
        reply="椭圆示意如下：",
    )
    fence = _append_math_sketch_fence(state)
    assert "jnao-svg" in fence
    assert "jnao-svg" in (state.reply or "")
