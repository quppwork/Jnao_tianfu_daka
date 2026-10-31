"""百炼知识问答 — POST /api/v2/apps/knowledge/chat（SSE）。

控制台「知识问答服务」发布后得到的 aid-* 在此调用；不在代码侧叠加人设或 KB 提示词。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.logger import get_logger
from app.services.bailian.config import BailianConfig, load_bailian_config

logger = get_logger("bailian.knowledge_chat")


@dataclass
class RetrievedDoc:
    text: str = ""
    score: float | None = None
    doc_name: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeChatResult:
    reply: str
    aid: str
    request_id: str | None = None
    usage: dict[str, Any] | None = None
    retrieved_docs: list[RetrievedDoc] = field(default_factory=list)
    planning_text: str = ""
    stages: list[str] = field(default_factory=list)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "reply": self.reply,
            "aid": self.aid,
            "request_id": self.request_id,
            "reply_len": len(self.reply or ""),
            "usage": self.usage,
            "retrieved_doc_count": len(self.retrieved_docs),
            "stages": self.stages,
            "planning_len": len(self.planning_text or ""),
        }


@dataclass
class _SseAccum:
    reply_parts: list[str] = field(default_factory=list)
    planning_parts: list[str] = field(default_factory=list)
    stages: list[str] = field(default_factory=list)
    docs: list[RetrievedDoc] = field(default_factory=list)
    request_id: str | None = None
    usage: dict[str, Any] | None = None
    error: str | None = None


def knowledge_chat_url(cfg: BailianConfig | None = None) -> str:
    c = cfg or load_bailian_config()
    host = (c.api_host or "").rstrip("/")
    if not host:
        ws = (c.workspace_id or "").strip()
        host = f"https://{ws}.cn-beijing.maas.aliyuncs.com" if ws else ""
    elif not host.startswith("http"):
        host = f"https://{host}"
    return f"{host}/api/v2/apps/knowledge/chat"


def _content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content)


def _extract_docs(extra_json: Any) -> list[RetrievedDoc]:
    if not isinstance(extra_json, dict):
        return []
    docs_raw = extra_json.get("docs") or extra_json.get("data") or []
    if not isinstance(docs_raw, list):
        return []
    out: list[RetrievedDoc] = []
    for d in docs_raw:
        if not isinstance(d, dict):
            continue
        meta = d.get("metadata") if isinstance(d.get("metadata"), dict) else {}
        text = (
            d.get("text")
            or d.get("content")
            or meta.get("content")
            or ""
        )
        text = str(text).strip()
        if not text:
            continue
        score = d.get("score")
        try:
            score_f = float(score) if score is not None else None
        except (TypeError, ValueError):
            score_f = None
        out.append(
            RetrievedDoc(
                text=text,
                score=score_f,
                doc_name=str(meta.get("doc_name") or d.get("doc_name") or ""),
                raw=d,
            )
        )
    return out


def _ingest_sse_line(accum: _SseAccum, raw_line: str) -> str | None:
    """吃掉一行 SSE；若是 generating 增量则返回该段文本，否则 None。"""
    line = raw_line.strip()
    if not line:
        return None
    if line.startswith("event:"):
        if "error" in line.lower():
            accum.error = accum.error or "sse_error_event"
        return None
    if not line.startswith("data:"):
        return None
    payload = line[5:].strip()
    if not payload or payload == "[DONE]":
        return None
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if isinstance(event, dict) and event.get("code") and str(event.get("code")) != "200":
        accum.error = str(event.get("message") or event.get("code"))
        return None

    accum.request_id = str(event.get("request_id") or accum.request_id or "") or accum.request_id
    if event.get("usage"):
        accum.usage = event.get("usage")

    output = event.get("output") or {}
    if isinstance(output, dict) and output.get("request_id"):
        accum.request_id = str(output.get("request_id"))

    choices = []
    if isinstance(output, dict):
        choices = output.get("choices") or []
    if not choices and event.get("choices"):
        choices = event.get("choices") or []

    token_out: str | None = None
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        msg = choice.get("message") or {}
        if not isinstance(msg, dict):
            continue
        extra = msg.get("extra") or {}
        if not isinstance(extra, dict):
            extra = {}
        step = str(extra.get("step") or "")
        group = str(extra.get("group") or "")
        step_change = str(extra.get("step_change") or "")
        if step_change:
            accum.stages.append(step_change)

        add_kw = msg.get("additional_kwargs") or {}
        if isinstance(add_kw, dict):
            extra_json = add_kw.get("extra_json")
            accum.docs.extend(_extract_docs(extra_json))

        text = _content_text(msg.get("content"))
        if not text:
            continue
        if step == "generating" or group == "generating":
            accum.reply_parts.append(text)
            token_out = (token_out or "") + text
        elif step == "planning" or group == "planning":
            accum.planning_parts.append(text)
    return token_out


def _accum_to_parsed(accum: _SseAccum) -> dict[str, Any]:
    return {
        "reply": "".join(accum.reply_parts).strip(),
        "planning_text": "".join(accum.planning_parts).strip(),
        "retrieved_docs": list(accum.docs),
        "request_id": accum.request_id,
        "usage": accum.usage,
        "stages": list(accum.stages),
        "error": accum.error,
    }


def parse_knowledge_chat_sse(lines: Iterator[str]) -> dict[str, Any]:
    """解析 SSE 行，返回 reply / docs / meta（供单测）。"""
    accum = _SseAccum()
    for raw_line in lines:
        _ingest_sse_line(accum, raw_line)
    return _accum_to_parsed(accum)


def iter_knowledge_chat_sse_tokens(lines: Iterator[str]) -> Iterator[tuple[str, Any]]:
    """解析 SSE：yield ('token', str) 增量；最后 yield ('parsed', dict)。"""
    accum = _SseAccum()
    for raw_line in lines:
        token = _ingest_sse_line(accum, raw_line)
        if token:
            yield ("token", token)
    yield ("parsed", _accum_to_parsed(accum))


def _build_payload(
    query: str,
    *,
    aid: str,
    messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    q = (query or "").strip()
    msgs = messages or [{"role": "user", "content": [{"type": "text", "text": q}]}]
    return {
        "input": {"messages": msgs},
        "parameters": {"agent_options": {"agent_id": aid}},
        "stream": True,
    }


def _auth_headers(cfg: BailianConfig) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {cfg.dashscope_api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }


def _record_usage(
    *,
    query: str,
    agent_id: str,
    parsed: dict[str, Any],
    cfg: BailianConfig,
) -> None:
    try:
        from app.services.bailian.token_estimate import estimate_retrieve_tokens
        from app.services.usage_recorder import _parse_usage_dict, record_usage

        docs = parsed.get("retrieved_docs") or []
        usage = parsed.get("usage")
        est = estimate_retrieve_tokens(
            query,
            chunk_texts=[getattr(d, "text", "") or "" for d in docs],
            enable_reranking=True,
            prelim_top_k=max(50, int(cfg.dense_top_k or 50)),
            index_count=1,
        )
        p_llm, c_llm, t_llm = _parse_usage_dict(usage if isinstance(usage, dict) else None)
        prompt = est.query_embed_tokens + p_llm
        completion = est.rerank_tokens + c_llm
        total = est.total_tokens + (t_llm if t_llm else (p_llm + c_llm))
        reply = parsed.get("reply") or ""
        record_usage(
            provider="bailian",
            api="knowledge_chat",
            model=agent_id,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            metric_kind="mixed" if (p_llm or c_llm or t_llm) else "est_rag",
            call_count=1,
            doc_count=len(docs),
            estimated=True,
            feature="rag",
            request_id=parsed.get("request_id"),
            ok=bool(reply),
        )
    except Exception as e:
        logger.warning("bailian knowledge_chat usage record skipped: %s", e)


def _result_from_parsed(
    parsed: dict[str, Any],
    *,
    agent_id: str,
) -> KnowledgeChatResult | None:
    if parsed.get("error"):
        logger.warning("knowledge_chat sse error aid=%s err=%s", agent_id, parsed["error"])
        return None
    reply = parsed.get("reply") or ""
    if not reply:
        logger.warning(
            "knowledge_chat empty reply aid=%s stages=%s",
            agent_id,
            parsed.get("stages"),
        )
    return KnowledgeChatResult(
        reply=reply,
        aid=agent_id,
        request_id=parsed.get("request_id"),
        usage=parsed.get("usage"),
        retrieved_docs=parsed.get("retrieved_docs") or [],
        planning_text=parsed.get("planning_text") or "",
        stages=parsed.get("stages") or [],
    )


def knowledge_chat_sync(
    query: str,
    *,
    aid: str,
    cfg: BailianConfig | None = None,
    messages: list[dict[str, Any]] | None = None,
    timeout: float = 90,
) -> KnowledgeChatResult | None:
    """同步调用知识问答；内部仍走 SSE，结束后返回整段 reply。"""
    c = cfg or load_bailian_config()
    q = (query or "").strip()
    agent_id = (aid or "").strip()
    if not q or not agent_id:
        return None
    if not (c.workspace_id and c.dashscope_api_key):
        logger.warning("knowledge_chat not configured (workspace/dashscope key)")
        return None

    payload = _build_payload(q, aid=agent_id, messages=messages)
    headers = _auth_headers(c)
    url = knowledge_chat_url(c)
    parsed: dict[str, Any] | None = None

    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    body = resp.read().decode("utf-8", errors="replace")
                    logger.warning(
                        "knowledge_chat HTTP %s aid=%s body=%s",
                        resp.status_code,
                        agent_id,
                        body[:400],
                    )
                    return None
                for kind, payload_evt in iter_knowledge_chat_sse_tokens(resp.iter_lines()):
                    if kind == "parsed":
                        parsed = payload_evt
    except httpx.TimeoutException as e:
        logger.warning("knowledge_chat timeout aid=%s err=%s", agent_id, e)
        return None
    except Exception as e:
        logger.warning("knowledge_chat failed aid=%s err=%s", agent_id, e)
        return None

    if not parsed:
        return None
    _record_usage(query=q, agent_id=agent_id, parsed=parsed, cfg=c)
    return _result_from_parsed(parsed, agent_id=agent_id)


async def knowledge_chat_stream(
    query: str,
    *,
    aid: str,
    cfg: BailianConfig | None = None,
    messages: list[dict[str, Any]] | None = None,
    timeout: float = 90,
) -> AsyncIterator[tuple[str, Any]]:
    """异步流式：yield ('token', str) 增量，最后 yield ('result', KnowledgeChatResult|None)。"""
    c = cfg or load_bailian_config()
    q = (query or "").strip()
    agent_id = (aid or "").strip()
    if not q or not agent_id:
        yield ("result", None)
        return
    if not (c.workspace_id and c.dashscope_api_key):
        logger.warning("knowledge_chat not configured (workspace/dashscope key)")
        yield ("result", None)
        return

    payload = _build_payload(q, aid=agent_id, messages=messages)
    headers = _auth_headers(c)
    url = knowledge_chat_url(c)
    accum = _SseAccum()

    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", errors="replace")
                    logger.warning(
                        "knowledge_chat HTTP %s aid=%s body=%s",
                        resp.status_code,
                        agent_id,
                        body[:400],
                    )
                    yield ("result", None)
                    return
                async for line in resp.aiter_lines():
                    token = _ingest_sse_line(accum, line)
                    if token:
                        yield ("token", token)
    except httpx.TimeoutException as e:
        logger.warning("knowledge_chat timeout aid=%s err=%s", agent_id, e)
        yield ("result", None)
        return
    except Exception as e:
        logger.warning("knowledge_chat failed aid=%s err=%s", agent_id, e)
        yield ("result", None)
        return

    parsed = _accum_to_parsed(accum)
    _record_usage(query=q, agent_id=agent_id, parsed=parsed, cfg=c)
    yield ("result", _result_from_parsed(parsed, agent_id=agent_id))
