"""OpenAI 兼容 tool schema / tool_calls 解析（与 Guide planner 同形，面向 Harness 注册表）。"""

from __future__ import annotations

import json
from typing import Any

from app.harness.catalog import aggregated_tools
from app.harness.types import ToolSpec


def openai_tools_for_profile(profile: str | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for spec in aggregated_tools(profile=profile):
        out.append(_schema(spec))
    return out


def _schema(spec: ToolSpec) -> dict[str, Any]:
    params = spec.input_schema or {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": params,
        },
    }


def parse_tool_calls(message: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(message, dict):
        return []
    raw = message.get("tool_calls")
    if not isinstance(raw, list):
        fc = message.get("function_call")
        raw = [{"type": "function", "function": fc}] if isinstance(fc, dict) else []
    out: list[dict[str, Any]] = []
    for call in raw:
        if not isinstance(call, dict):
            continue
        fn = call.get("function") if isinstance(call.get("function"), dict) else call
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        args_raw = fn.get("arguments") or "{}"
        if isinstance(args_raw, dict):
            args = args_raw
        else:
            try:
                args = json.loads(args_raw) if args_raw else {}
            except json.JSONDecodeError:
                args = {}
        if not isinstance(args, dict):
            args = {}
        out.append(
            {
                "id": str(call.get("id") or name),
                "name": name,
                "args": args,
            }
        )
    return out
