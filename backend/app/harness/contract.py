"""工具入参契约校验 — 参数合不合法。

对照外部 MCP（Zod + SDK）的「契约层」：此处用 ToolSpec.input_schema（JSON Schema 子集）
在 call_tool 入口强制校验。后续可换成 jsonschema Draft，或由外部 SDK 的 schema 生成同构校验。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContractError:
    """入参不合 schema。"""

    tool: str
    message: str
    path: str = ""

    def as_text(self) -> str:
        loc = f" @ {self.path}" if self.path else ""
        return f"contract:{self.tool}{loc}: {self.message}"


def validate_tool_args(
    tool: str,
    schema: dict[str, Any] | None,
    args: dict[str, Any] | None,
) -> ContractError | None:
    """校验 args 是否符合 inputSchema。通过返回 None。"""
    payload = dict(args or {})
    if not schema or not isinstance(schema, dict):
        return None
    return _validate_node(tool, schema, payload, path="$")


def _validate_node(
    tool: str,
    schema: dict[str, Any],
    value: Any,
    *,
    path: str,
) -> ContractError | None:
    expected = schema.get("type")
    if expected == "object" or (
        expected is None and ("properties" in schema or "required" in schema)
    ):
        if not isinstance(value, dict):
            return ContractError(tool, f"expected object, got {type(value).__name__}", path)
        props = schema.get("properties") or {}
        required = schema.get("required") or []
        for key in required:
            if key not in value:
                return ContractError(tool, f"missing required '{key}'", f"{path}.{key}")
        for key, child in value.items():
            if key in props and isinstance(props[key], dict):
                err = _validate_node(tool, props[key], child, path=f"{path}.{key}")
                if err:
                    return err
            elif schema.get("additionalProperties") is False and key not in props:
                return ContractError(tool, f"unexpected property '{key}'", f"{path}.{key}")
        return None

    if expected == "array":
        if not isinstance(value, list):
            return ContractError(tool, f"expected array, got {type(value).__name__}", path)
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                err = _validate_node(tool, item_schema, item, path=f"{path}[{i}]")
                if err:
                    return err
        return None

    if expected == "string":
        if not isinstance(value, str):
            return ContractError(tool, f"expected string, got {type(value).__name__}", path)
        return None
    if expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            # JSON 常把整型写成 float
            if isinstance(value, float) and value.is_integer():
                return None
            return ContractError(tool, f"expected integer, got {type(value).__name__}", path)
        return None
    if expected == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return ContractError(tool, f"expected number, got {type(value).__name__}", path)
        return None
    if expected == "boolean":
        if not isinstance(value, bool):
            return ContractError(tool, f"expected boolean, got {type(value).__name__}", path)
        return None
    if expected == "null":
        if value is not None:
            return ContractError(tool, f"expected null, got {type(value).__name__}", path)
        return None

    # 未声明 type：放行（兼容空 schema / 逐步收紧）
    return None
