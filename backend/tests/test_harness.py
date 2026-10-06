"""Harness：本地 MCP + 沙箱；retrieve_kb 为共享 Tool。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.harness.mcp_protocol import handle_rpc
from app.harness.registry import reset_registry_for_tests
from app.harness.runtime import call_tool, harness_status


@pytest.fixture(autouse=True)
def _local_sandbox(monkeypatch):
    monkeypatch.setenv("HARNESS_SANDBOX", "local")
    monkeypatch.setenv("HARNESS_MCP_HTTP", "1")
    reset_registry_for_tests()
    yield
    reset_registry_for_tests()


@pytest.mark.asyncio
async def test_sandbox_ping_local_process():
    result = await call_tool("sandbox.ping", {"token": "hi"}, profile="harness")
    assert result.ok is True
    assert result.data.get("pong") == "hi"
    assert result.data.get("via") == "sandbox"
    assert result.isolation.startswith("process:local")


@pytest.mark.asyncio
async def test_retrieve_kb_uses_bailian_query():
    fake = type("R", (), {})()
    fake.rag_block = "[1] 超脑阅读\n每天练"
    fake.nodes = [
        type("N", (), {"score": 0.9, "text": "每天练", "title": "教法", "doc_name": "教法"})()
    ]
    fake.mode = "retrieve"

    with patch(
        "app.services.bailian.guide_rag_query",
        new=AsyncMock(return_value=fake),
    ):
        result = await call_tool("retrieve_kb", {"query": "怎么练超脑阅读"}, profile="consult")
    assert result.ok is True
    assert result.data["rag_used"] is True
    assert "每天练" in result.data["rag_block"]
    assert result.data["kb_hits"]


@pytest.mark.asyncio
async def test_profile_whitelist():
    result = await call_tool("sandbox.ping", {"token": "x"}, profile="consult")
    assert result.ok is False
    assert "consult" in (result.error or "")


@pytest.mark.asyncio
async def test_mcp_initialize_list_call():
    init = await handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "jnao-harness"
    listed = await handle_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {t["name"] for t in listed["result"]["tools"]}
    assert "retrieve_kb" in names
    assert "sandbox.ping" in names
    called = await handle_rpc(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "sandbox.ping", "arguments": {"token": "mcp"}},
        }
    )
    assert called["result"]["isError"] is False
    assert "mcp" in called["result"]["content"][0]["text"]


def test_health_and_http_mcp(client: TestClient):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert "harness" in health.json()["integrations"]
    st = client.get("/api/harness/status")
    assert st.status_code == 200
    assert "retrieve_kb" in st.json()["tools"]
    body = client.post(
        "/api/harness/mcp",
        json={"jsonrpc": "2.0", "id": 9, "method": "ping"},
    )
    assert body.status_code == 200
    assert body.json()["result"] == {}
    sb = client.get("/api/harness/sandbox")
    assert sb.status_code == 200
    assert sb.json()["data_plane"]["executor"] == "harness_sandbox_agent"


def test_harness_status_shape():
    st = harness_status()
    assert st["sandbox"] == "local"
    assert "retrieve_kb" in st["tools"]
    assert st["control_plane"]["network"] == "none"
    assert st["control_plane"]["docker_sock_mounted"] is False
    assert st["data_plane"]["channel"] == "json-stdio"
    assert st["agent_loop"]["pattern"] == "model-tool-interrupt"


@pytest.mark.asyncio
async def test_gateway_denies_shell_and_python():
    from app.harness.gateway import invoke_async

    py = await invoke_async("python", {"code": "print(1)"})
    assert py.status == "denied"
    sh = await invoke_async("shell", {"cmd": "echo hi"})
    assert sh.status == "denied"


def test_sandbox_session_token_and_destroy():
    from app.harness.control import controller
    from app.harness.gateway import invoke
    from app.harness.protocol import ToolCall

    sess = controller.create()
    try:
        bad = invoke("sandbox.ping", {"token": "x"}, session=sess, token="wrong")
        assert bad.status == "denied"
        ok = invoke("sandbox.ping", {"token": "x"}, session=sess, token=sess.token)
        assert ok.status == "success"
        assert ok.data.get("pong") == "x"
        health = controller.exec(
            sess, ToolCall(tool="sandbox.health", args={}, timeout_ms=3000, call_id="h")
        )
        assert health.ok
    finally:
        controller.destroy(sess)
    assert controller.get(sess.id) is None


@pytest.mark.asyncio
async def test_mcp_catalog_hides_sandbox_tools_for_consult():
    listed = await handle_rpc(
        {"jsonrpc": "2.0", "id": 4, "method": "tools/list"},
        profile="consult",
    )
    names = {t["name"] for t in listed["result"]["tools"]}
    assert "retrieve_kb" in names
    assert "sandbox.ping" not in names


@pytest.mark.asyncio
async def test_sandbox_deny_blocks_mcp_loopback(monkeypatch):
    monkeypatch.setenv("HARNESS_SANDBOX_DENY", "sandbox.ping")
    from app.harness.client import GatewayMCPClient

    client = GatewayMCPClient(profile="harness")
    listed = {t["name"] for t in client.list_tools()}
    assert "sandbox.ping" not in listed
    result = await client.call_tool("sandbox.ping", {"token": "nope"})
    assert result.ok is False
    assert "sandbox.deny" in (result.error or "")


@pytest.mark.asyncio
async def test_host_plane_retrieve_not_in_sandbox_server():
    from app.harness.catalog import tools_for_server
    from app.harness.client import GatewayMCPClient

    host = {t.name for t in tools_for_server("jnao-host")}
    sbx = {t.name for t in tools_for_server("jnao-sandbox")}
    assert "retrieve_kb" in host
    assert "retrieve_kb" not in sbx
    assert "sandbox.ping" in sbx
    desc = GatewayMCPClient(profile="consult").describe()
    assert "retrieve_kb" in desc["host_tools"]
    assert "sandbox.ping" not in desc["sandbox_tools"]


@pytest.mark.asyncio
async def test_teacher_catalog_and_confirm_write():
    listed = await handle_rpc(
        {"jsonrpc": "2.0", "id": 10, "method": "tools/list"},
        profile="teacher",
    )
    names = {t["name"] for t in listed["result"]["tools"]}
    assert "list_academy_courses" in names
    assert "create_course" in names
    assert "retrieve_kb" not in names

    pending = await call_tool("create_course", {"title": "测验课"}, profile="teacher")
    assert pending.ok is False
    assert pending.data.get("needs_confirm") is True
    token = pending.data["confirm_token"]
    done = await call_tool(
        "create_course",
        {"confirm_token": token},
        profile="teacher",
    )
    assert done.ok is False
    assert "不落" in (done.error or done.data.get("error") or "") or "LMS" in (
        done.error or done.data.get("error") or ""
    )

    blocked = await call_tool("create_course", {"title": "x"}, profile="parent_guide")
    assert blocked.ok is False

    courses = await call_tool("list_academy_courses", {}, profile="teacher")
    assert courses.ok is True
    assert courses.data.get("courses")


@pytest.mark.asyncio
async def test_socratic_skips_without_llm():
    result = await call_tool(
        "generate_socratic_hint",
        {"question": "1+1为什么等于2"},
        profile="qa",
    )
    assert result.ok is True
    assert result.data.get("skipped") is True or result.data.get("text")
