"""RAG 工具契约 — 入参 / 出参校验，与业务 prompt 解耦。

RAG 只返回检索切片，不生成对用户的最终答复。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.harness.contract import ContractError, validate_tool_args
from app.services.kb_policy import DEFAULT_ACTIVE_INDEX_ID, DEFAULT_ACTIVE_SOURCE_KEY

TALENT_DOC_SOURCE_KEY = DEFAULT_ACTIVE_SOURCE_KEY
TALENT_DOC_INDEX_ID = DEFAULT_ACTIVE_INDEX_ID

TALENT_DOC_RETRIEVE_INPUT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "检索问句，围绕天赋报告 / 五者 / 库内练法",
        },
        "top_n": {
            "type": "integer",
            "description": "最多返回条数，默认 3，上限 8",
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}

TALENT_DOC_RETRIEVE_OUTPUT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "source_key": {"type": "string"},
        "index_id": {"type": "string"},
        "query": {"type": "string"},
        "hit_count": {"type": "integer"},
        "hits": {"type": "array"},
        "citations": {"type": "array"},
        "request_id": {"type": "string"},
        "error": {"type": "string"},
        "error_kind": {"type": "string"},
    },
    "required": ["ok", "source_key", "index_id", "query", "hit_count", "hits"],
    "additionalProperties": True,
}


@dataclass(frozen=True)
class RagContractViolation:
    phase: str  # input | output | runtime
    message: str
    path: str = ""

    def as_text(self) -> str:
        loc = f" @ {self.path}" if self.path else ""
        return f"rag_contract[{self.phase}]{loc}: {self.message}"


def validate_talent_doc_input(args: dict[str, Any] | None) -> RagContractViolation | None:
    err = validate_tool_args("talent_doc_retrieve", TALENT_DOC_RETRIEVE_INPUT, args)
    if err:
        return RagContractViolation("input", err.message, err.path)
    query = str((args or {}).get("query") or "").strip()
    if not query:
        return RagContractViolation("input", "query 不能为空", "$.query")
    if len(query) > 2000:
        return RagContractViolation("input", "query 过长", "$.query")
    top_n = (args or {}).get("top_n")
    if top_n is not None:
        try:
            n = int(top_n)
        except (TypeError, ValueError):
            return RagContractViolation("input", "top_n 必须是整数", "$.top_n")
        if n < 1 or n > 8:
            return RagContractViolation("input", "top_n 须在 1–8", "$.top_n")
    return None


def validate_talent_doc_output(payload: dict[str, Any] | None) -> RagContractViolation | None:
    data = payload if isinstance(payload, dict) else None
    if data is None:
        return RagContractViolation("output", "结果必须是 object")
    err = validate_tool_args("talent_doc_retrieve.out", TALENT_DOC_RETRIEVE_OUTPUT, data)
    if err:
        return RagContractViolation("output", err.message, err.path)
    if data.get("source_key") != TALENT_DOC_SOURCE_KEY:
        return RagContractViolation(
            "output",
            f"source_key 必须是 {TALENT_DOC_SOURCE_KEY}",
            "$.source_key",
        )
    if data.get("index_id") != TALENT_DOC_INDEX_ID:
        return RagContractViolation(
            "output",
            f"index_id 必须是 {TALENT_DOC_INDEX_ID}",
            "$.index_id",
        )
    hits = data.get("hits")
    if not isinstance(hits, list):
        return RagContractViolation("output", "hits 必须是数组", "$.hits")
    hit_count = int(data.get("hit_count") or 0)
    if hit_count != len(hits):
        return RagContractViolation(
            "output",
            "hit_count 与 hits 长度不一致",
            "$.hit_count",
        )
    if bool(data.get("ok")) and hit_count <= 0 and not data.get("error"):
        return RagContractViolation(
            "output",
            "ok=true 时必须有命中，或显式 error",
            "$.ok",
        )
    for i, hit in enumerate(hits):
        if not isinstance(hit, dict):
            return RagContractViolation("output", "hit 必须是 object", f"$.hits[{i}]")
        text = str(hit.get("text") or "").strip()
        if not text:
            return RagContractViolation("output", "hit.text 不能为空", f"$.hits[{i}].text")
    return None


def fail_payload(
    *,
    query: str,
    error: str,
    error_kind: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "source_key": TALENT_DOC_SOURCE_KEY,
        "index_id": TALENT_DOC_INDEX_ID,
        "query": query,
        "hit_count": 0,
        "hits": [],
        "error": error,
        "error_kind": error_kind,
    }
