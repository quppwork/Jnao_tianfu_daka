"""SSE 流式响应工具"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def sse_json(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_done() -> str:
    return "data: [DONE]\n\n"


async def emit_event_stream(
    gen: AsyncIterator[tuple[str, Any]],
) -> AsyncIterator[str]:
    """将 (kind, payload) 生成器转为 SSE 文本流。

    kind: token | done | error
    """
    async for kind, payload in gen:
        if kind == "token":
            yield sse_json({"type": "token", "content": payload})
        elif kind == "done":
            meta = payload if isinstance(payload, dict) else {}
            yield sse_json({"type": "done", **meta})
        elif kind == "error":
            msg = str(payload)
            if msg.startswith("[ERROR]"):
                msg = msg.replace("[ERROR]", "", 1).strip()
            yield sse_json({"type": "error", "message": msg})
    yield sse_done()
