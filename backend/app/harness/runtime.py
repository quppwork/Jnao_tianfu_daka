"""单次 tool 调用 — Agent 走这里，不直接碰百炼/子进程。"""

from __future__ import annotations

import inspect
import logging
import time
from typing import Any

from app.harness.registry import get_tool, list_tool_specs
from app.harness.sandbox import SandboxError, run_isolated
from app.harness.settings import load_harness_settings
from app.harness.policy import check_tool
from app.harness.trace import emit as emit_trace
from app.harness.types import ToolResult

logger = logging.getLogger("jnao.harness")


def _traced(result: ToolResult, *, profile: str | None) -> ToolResult:
    emit_trace(
        result.name,
        result.duration_ms,
        result.ok,
        profile=profile or "",
        error=result.error,
    )
    return result


def _with_evidence(
    result: ToolResult,
    *,
    profile: str | None,
    record: bool,
) -> ToolResult:
    """结果入 Evidence 账本（可关 HARNESS_EVIDENCE=0）。"""
    if not record:
        return result
    try:
        from app.harness.evidence import create_evidence

        body = dict(result.data)
        if result.error:
            body.setdefault("error", result.error)
        ev = create_evidence(
            tool=result.name,
            payload=body,
            ok=result.ok,
            profile=profile or "",
            meta={"isolation": result.isolation, "duration_ms": result.duration_ms},
        )
        result.evidence_id = ev.id
        result.content_sha256 = ev.content_sha256
        if isinstance(result.data, dict):
            result.data = {**result.data, "evidence_id": ev.id, "content_sha256": ev.content_sha256}
    except Exception:
        logger.exception("evidence record failed for %s", result.name)
    return result


async def call_tool(
    name: str,
    args: dict[str, Any] | None = None,
    *,
    profile: str | None = None,
    ctx: Any | None = None,
) -> ToolResult:
    from app.harness import approval
    from app.harness.context import (
        ToolContext,
        bind_context,
        context_from_args,
        reset_context,
    )
    from app.harness.contract import validate_tool_args

    t0 = time.perf_counter()
    cfg = load_harness_settings()
    spec = get_tool(name)
    payload = dict(args or {})
    if spec is None:
        return _traced(
            ToolResult(ok=False, name=name, error=f"unknown tool {name}"),
            profile=profile,
        )
    decision = check_tool(spec, name, profile=profile)
    if not decision.allowed:
        return _traced(
            ToolResult(
                ok=False,
                name=name,
                error=decision.reason,
                isolation=spec.isolation,
                duration_ms=int((time.perf_counter() - t0) * 1000),
            ),
            profile=profile,
        )

    if cfg.contract_validate:
        cerr = validate_tool_args(name, spec.input_schema, payload)
        if cerr:
            return _traced(
                ToolResult(
                    ok=False,
                    name=name,
                    error=cerr.as_text(),
                    isolation=spec.isolation,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                ),
                profile=profile,
            )

    if spec.permission == "confirm":
        token = str(payload.pop("confirm_token", "") or "")
        if token:
            row = approval.consume(token)
            if not row or row.get("tool") != name:
                return _traced(
                    ToolResult(ok=False, name=name, error="invalid confirm_token"),
                    profile=profile,
                )
            payload = dict(row.get("args") or {})
            payload["confirmed"] = True
        else:
            issued = approval.issue(name, payload, profile=profile or "")
            return _traced(
                ToolResult(
                    ok=False,
                    name=name,
                    error="needs_confirm",
                    data={
                        "needs_confirm": True,
                        "confirm_token": issued,
                        "tool": name,
                    },
                    isolation=spec.isolation,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                ),
                profile=profile,
            )

    isolation = spec.isolation
    built = ctx if isinstance(ctx, ToolContext) else context_from_args(payload, profile=profile)
    if not built.profile:
        built.profile = profile or ""
    opened_db = False
    if spec.needs_db and built.db is None:
        from app.db.session import get_session_factory

        built.db = get_session_factory()()
        opened_db = True
    tok = bind_context(built)
    try:
        if isolation == "process" or spec.plane == "sandbox":
            data = await run_isolated({"tool": spec.name, "args": payload})
            ok = bool(data.get("ok", True))
            err = None if ok else str(data.get("error") or "sandbox failed")
            ms = int((time.perf_counter() - t0) * 1000)
            return _traced(
                _with_evidence(
                    ToolResult(
                        ok=ok,
                        name=name,
                        data=data if isinstance(data, dict) else {"result": data},
                        error=err,
                        isolation=f"process:{cfg.sandbox}",
                        duration_ms=ms,
                    ),
                    profile=profile,
                    record=cfg.evidence_record,
                ),
                profile=profile,
            )

        raw = spec.handler(payload)
        if inspect.isawaitable(raw):
            raw = await raw
        data = raw if isinstance(raw, dict) else {"result": raw}
        ok = bool(data.get("ok", True))
        err = None if ok else str(data.get("error") or "tool failed")
        ms = int((time.perf_counter() - t0) * 1000)
        return _traced(
            _with_evidence(
                ToolResult(
                    ok=ok,
                    name=name,
                    data=data,
                    error=err,
                    isolation="none",
                    duration_ms=ms,
                ),
                profile=profile,
                record=cfg.evidence_record,
            ),
            profile=profile,
        )
    except SandboxError as e:
        logger.warning("harness sandbox %s: %s", name, e)
        ms = int((time.perf_counter() - t0) * 1000)
        return _traced(
            _with_evidence(
                ToolResult(
                    ok=False,
                    name=name,
                    error=str(e)[:300],
                    isolation=f"process:{cfg.sandbox}",
                    duration_ms=ms,
                ),
                profile=profile,
                record=cfg.evidence_record,
            ),
            profile=profile,
        )
    except Exception as e:
        logger.exception("harness tool %s failed", name)
        ms = int((time.perf_counter() - t0) * 1000)
        return _traced(
            _with_evidence(
                ToolResult(
                    ok=False,
                    name=name,
                    error=str(e)[:300],
                    isolation=isolation,
                    duration_ms=ms,
                ),
                profile=profile,
                record=cfg.evidence_record,
            ),
            profile=profile,
        )
    finally:
        reset_context(tok)
        if opened_db and built.db is not None:
            built.db.close()


def harness_status() -> dict[str, Any]:
    cfg = load_harness_settings()
    from app.harness.catalog import catalog_status
    from app.harness.control import controller
    from app.harness.mcp_adapters import get_adapter_registry

    return {
        "sandbox": cfg.sandbox,
        "sandbox_image": cfg.sandbox_image,
        "mcp_transport": cfg.mcp_transport,
        "tools": [t.name for t in list_tool_specs()],
        "server": cfg.server_name,
        "version": cfg.server_version,
        "contract_validate": cfg.contract_validate,
        "evidence_record": cfg.evidence_record,
        "external_mcp_adapters": get_adapter_registry().list_adapters(),
        "control_plane": {
            "runtime": cfg.sandbox,
            "keepalive": cfg.keepalive,
            "memory_mb": cfg.sandbox_memory_mb,
            "pids": cfg.sandbox_pids,
            "network": "none",
            "sessions": controller.list_sessions(),
            "docker_sock_mounted": False,
        },
        "data_plane": {
            "channel": "json-stdio",
            "executor": "harness_sandbox_agent",
            "max_result_bytes": cfg.max_result_bytes,
            "mcp_in_sandbox": "stdio-loopback-equivalent",
            "listen_ports": [],
        },
        "mcp": catalog_status(),
        "agent_loop": {
            "pattern": "model-tool-interrupt",
            "refs": ["LangGraph ToolNode+interrupt", "OpenAI Agents SDK Runner", "Anthropic tool_use"],
            "max_steps_default": 6,
            "checkpoint": "memory-thread",
            "memory": "window_for_model",
            "llm_retry": 1,
            "stream": "iter_agent token",
            "orchestration": "handoff_packet",
        },
    }
