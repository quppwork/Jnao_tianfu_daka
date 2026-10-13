"""契约校验 + Evidence 账本 + 外部 MCP 适配骨架。"""

from __future__ import annotations

import pytest

from app.harness.contract import validate_tool_args
from app.harness.evidence import (
    MemoryEvidenceLedger,
    content_hash,
    create_evidence,
    get_ledger,
    set_ledger,
    verify_evidence,
)
from app.harness.mcp_adapters import (
    ExternalToolDesc,
    RemoteCallResult,
    get_adapter_registry,
    register_adapter,
)
from app.harness.registry import reset_registry_for_tests
from app.harness.runtime import call_tool


@pytest.fixture(autouse=True)
def _harness_env(monkeypatch):
    monkeypatch.setenv("HARNESS_SANDBOX", "local")
    monkeypatch.setenv("HARNESS_CONTRACT", "1")
    monkeypatch.setenv("HARNESS_EVIDENCE", "1")
    ledger = MemoryEvidenceLedger()
    set_ledger(ledger)
    reset_registry_for_tests()
    get_adapter_registry().clear()
    yield
    reset_registry_for_tests()
    get_adapter_registry().clear()
    set_ledger(MemoryEvidenceLedger())


def test_contract_required_and_types():
    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "timeout": {"type": "number"},
        },
        "required": ["query"],
        "additionalProperties": False,
    }
    assert validate_tool_args("t", schema, {"query": "hi"}) is None
    err = validate_tool_args("t", schema, {})
    assert err is not None
    assert "query" in err.message
    err2 = validate_tool_args("t", schema, {"query": "hi", "extra": 1})
    assert err2 is not None
    assert "extra" in err2.message
    err3 = validate_tool_args("t", schema, {"query": 1})
    assert err3 is not None


def test_evidence_hash_and_ledger():
    payload = {"ok": True, "hits": [1, 2]}
    ev = create_evidence(tool="demo", payload=payload, profile="qa")
    assert len(ev.content_sha256) == 64
    assert ev.content_sha256 == content_hash(payload)
    assert get_ledger().get(ev.id) is not None
    assert verify_evidence(ev, payload) is True
    assert verify_evidence(ev, {"ok": False}) is False


@pytest.mark.asyncio
async def test_call_tool_rejects_bad_contract():
    result = await call_tool(
        "retrieve_kb",
        {"query": "ok", "not_allowed": True},
        profile="consult",
    )
    assert result.ok is False
    assert result.error and result.error.startswith("contract:")


@pytest.mark.asyncio
async def test_call_tool_records_evidence():
    result = await call_tool("sandbox.ping", {"token": "ev"}, profile="harness")
    assert result.ok is True
    assert result.evidence_id
    assert result.content_sha256
    stored = get_ledger().get(result.evidence_id)
    assert stored is not None
    assert stored.tool == "sandbox.ping"
    assert stored.content_sha256 == result.content_sha256


@pytest.mark.asyncio
async def test_external_adapter_registry():
    class _Fake:
        name = "fake-mcp"

        async def list_tools(self):
            return [
                ExternalToolDesc(
                    name="remote.echo",
                    description="echo",
                    input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
                    server="fake-mcp",
                )
            ]

        async def call_tool(self, name, arguments=None):
            return RemoteCallResult(ok=True, data={"echo": (arguments or {}).get("q")})

    register_adapter(_Fake())
    reg = get_adapter_registry()
    assert reg.list_adapters() == ["fake-mcp"]
    tools = await reg.list_all_tools()
    assert tools[0].name == "remote.echo"
    out = await reg.call("remote.echo", {"q": "hi"}, server="fake-mcp")
    assert out.ok and out.data.get("echo") == "hi"
