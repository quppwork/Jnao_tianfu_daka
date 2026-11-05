"""联网轻量查证 — 抑制「今年高考压轴」等无依据断言。

优先 DuckDuckGo Instant Answer（无 key）；可配 TAVILY_API_KEY / SERPER_API_KEY。
"""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

from app.harness.registry import register_tool
from app.harness.types import ToolSpec

_QA_PROFILES = ("qa", "solve_science", "solve_language", "solve_humanities")


def _strip(s: str, n: int = 480) -> str:
    t = re.sub(r"\s+", " ", (s or "").strip())
    return t[:n]


def _max_results() -> int:
    try:
        n = int((os.getenv("WEB_SEARCH_MAX_RESULTS") or "5").strip())
    except ValueError:
        n = 5
    return max(1, min(n, 10))


def _timeout_seconds() -> float:
    try:
        t = float((os.getenv("WEB_SEARCH_TIMEOUT_SECONDS") or "12").strip())
    except ValueError:
        t = 12.0
    return max(3.0, min(t, 60.0))


async def _tavily(query: str) -> dict[str, Any] | None:
    key = (os.getenv("TAVILY_API_KEY") or "").strip()
    if not key or key.startswith("your-"):
        return None
    import httpx

    max_n = _max_results()
    timeout = _timeout_seconds()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": query,
                "max_results": max_n,
                "search_depth": "basic",
                "include_answer": True,
            },
        )
    if resp.status_code != 200:
        return {
            "provider": "tavily",
            "hits": [],
            "answer": "",
            "error": f"tavily HTTP {resp.status_code}: {(resp.text or '')[:160]}",
        }
    data = resp.json()
    hits = []
    for r in (data.get("results") or [])[:max_n]:
        hits.append(
            {
                "title": _strip(str(r.get("title") or ""), 120),
                "snippet": _strip(str(r.get("content") or r.get("snippet") or ""), 280),
                "url": str(r.get("url") or "")[:240],
            }
        )
    return {"provider": "tavily", "hits": hits, "answer": _strip(str(data.get("answer") or ""), 600)}


async def _duckduckgo(query: str) -> dict[str, Any]:
    import httpx

    max_n = _max_results()
    timeout = _timeout_seconds()
    url = f"https://api.duckduckgo.com/?q={quote(query)}&format=json&no_html=1&skip_disambig=1"
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "JNAO-QA/1.0"})
    hits: list[dict[str, Any]] = []
    answer = ""
    if resp.status_code == 200:
        data = resp.json()
        answer = _strip(str(data.get("AbstractText") or data.get("Answer") or ""), 600)
        for t in (data.get("RelatedTopics") or [])[:max_n]:
            if not isinstance(t, dict):
                continue
            text = _strip(str(t.get("Text") or ""), 280)
            if not text:
                continue
            hits.append(
                {
                    "title": text[:80],
                    "snippet": text,
                    "url": str(t.get("FirstURL") or "")[:240],
                }
            )
    return {"provider": "duckduckgo", "hits": hits, "answer": answer}


async def web_lookup(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    if not query:
        return {"ok": False, "error": "query 不能为空", "hits": []}
    # 收窄高考/出处类查询，避免过宽
    intent = str(args.get("intent") or "").strip()
    q = query
    if intent == "exam_source":
        q = f"{query} 出处 真题 年份"

    try:
        packed = await _tavily(q)
        # tavily 未配置 / 硬失败时回落 DDG；有 error 但仍无 hits 也回落
        if packed is None or (not packed.get("hits") and not packed.get("answer")):
            if packed and packed.get("error"):
                # 保留 tavily 错误信息供排查，但仍尝试 DDG
                ddg = await _duckduckgo(q)
                if ddg.get("hits") or ddg.get("answer"):
                    packed = ddg
                else:
                    packed = {**ddg, "error": packed.get("error")}
            else:
                packed = await _duckduckgo(q)
    except Exception as e:
        return {"ok": False, "error": f"lookup failed: {e}"[:200], "hits": []}

    hits = list(packed.get("hits") or [])
    answer = packed.get("answer") or ""
    verified = bool(answer or hits)
    return {
        "ok": True,
        "query": query,
        "provider": packed.get("provider"),
        "answer": answer,
        "hits": hits,
        "verified": verified,
        "guidance": (
            "若 hits/answer 无法证实「某年高考第几题」，回答中禁止断言具体卷别/题号；"
            "可改为「这类压轴数列题常见于竞赛/高考压轴风格」，并基于题干本身讲解。"
            if not verified
            else "请只引用能被 hits 支持的出处信息；不确定则不写死年份题号。"
        ),
    }


_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "检索问句；查真题时含题干关键词+年份/卷别",
        },
        "intent": {
            "type": "string",
            "description": "exam_source=查真题出处；general=一般查证（默认）",
            "enum": ["exam_source", "general"],
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}


def register() -> None:
    common = dict(
        input_schema=_INPUT_SCHEMA,
        permission="readonly",
        profiles=_QA_PROFILES,
        plane="host",
        mcp_server="jnao-host",
    )
    register_tool(
        ToolSpec(
            name="web_lookup",
            description=(
                "【jnao-host】联网查证（Tavily→DuckDuckGo）。"
                "断言「今年高考/某省卷第几题/出处年份」前必须调用；"
                "verified=false 时禁止写死卷别题号，只按题干讲。"
            ),
            handler=web_lookup,
            **common,
        )
    )
    # 别名：模型常喊 web_search
    register_tool(
        ToolSpec(
            name="web_search",
            description="联网查证（web_lookup 别名）。",
            handler=web_lookup,
            **common,
        )
    )
