"""Agent / MCP 可调用工具：百炼「知识问答」直出。

定位（对齐 What Now）：
- 这是 **Agent 工具**（Tool Registry / MCP jnao-host），不是 Harness 守卫。
- Harness 只负责：调用次数、超时、失败审计、熔断；不认识业务话术。
- 拒答 / 防注入由控制台知识问答应用配置；工具原样返回 reply。
"""

from __future__ import annotations

from typing import Any

from app.harness.registry import register_tool
from app.harness.types import ToolSpec
from app.services.kb_policy import knowledge_qa_aid


async def knowledge_qa(args: dict[str, Any]) -> dict[str, Any]:
    """调用百炼 knowledge/chat；成功时 data.reply 即对用户可见正文。"""
    from app.core.async_workers import run_sync
    from app.services.bailian.config import load_bailian_config
    from app.services.bailian.knowledge_chat import knowledge_chat_sync

    query = str((args or {}).get("query") or "").strip()
    if not query:
        return {"ok": False, "error": "query 不能为空", "error_kind": "input"}

    aid = str((args or {}).get("aid") or knowledge_qa_aid()).strip()
    if not aid:
        return {"ok": False, "error": "未配置知识问答 aid", "error_kind": "config"}

    cfg = load_bailian_config()
    if not (cfg.workspace_id and cfg.dashscope_api_key):
        return {
            "ok": False,
            "error": "knowledge_chat 未配置（需要 workspace + DASHSCOPE_API_KEY）",
            "error_kind": "config",
        }

    timeout = float((args or {}).get("timeout") or 90)
    try:
        result = await run_sync(
            knowledge_chat_sync, query, aid=aid, cfg=cfg, timeout=timeout
        )
    except Exception as e:
        return {
            "ok": False,
            "error": f"knowledge_chat failed: {type(e).__name__}",
            "error_kind": "runtime",
            "aid": aid,
        }

    reply = str(getattr(result, "reply", "") or "").strip() if result else ""
    if not result or not reply:
        return {
            "ok": False,
            "error": "知识问答无回复",
            "error_kind": "empty",
            "aid": aid,
            "request_id": getattr(result, "request_id", None) if result else None,
        }

    docs = []
    for d in list(getattr(result, "retrieved_docs", None) or [])[:5]:
        docs.append(
            {
                "text": (getattr(d, "text", None) or "")[:400],
                "score": getattr(d, "score", None),
                "doc_name": getattr(d, "doc_name", None) or "",
            }
        )
    return {
        "ok": True,
        "reply": reply,
        "aid": aid,
        "request_id": getattr(result, "request_id", None),
        "retrieved_docs": docs,
        "stages": list(getattr(result, "stages", None) or []),
    }


SPEC = ToolSpec(
    name="knowledge_qa",
    description=(
        "调用阿里云百炼「知识问答」应用（SSE 直出）。"
        "用户问天赋/课程/平台/五者/练法/家长课堂等，优先用本工具；"
        "返回的 reply 原样对用户说，不要改写。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "用户原问"},
            "aid": {
                "type": "string",
                "description": "可选；默认 BAILIAN_KB_QA_AID / 注册表 talent_doc.aid",
            },
            "timeout": {"type": "number", "description": "秒，默认 90"},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    handler=knowledge_qa,
    isolation="none",
    permission="readonly",
    profiles=("report_talent", "guide", "parent_guide"),
    plane="host",
    mcp_server="jnao-host",
)


def register() -> None:
    register_tool(SPEC)


register()
