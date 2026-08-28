"""百炼知识问答 — POST /api/v2/apps/knowledge/chat（SSE）。

控制台「知识问答服务」发布后得到的 aid-* 在此调用；不在代码侧叠加人设或 KB 提示词。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterator

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


def parse_knowledge_chat_sse(lines: Iterator[str]) -> dict[str, Any]:
    """解析 SSE 行，返回 reply / docs / meta（供单测）。"""
    reply_parts: list[str] = []
    planning_parts: list[str] = []
    stages: list[str] = []
    docs: list[RetrievedDoc] = []
    request_id: str | None = None
    usage: dict[str, Any] | None = None
    error: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("event:"):
            if "error" in line.lower():
                error = error or "sse_error_event"
            continue
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue

        if isinstance(event, dict) and event.get("code") and str(event.get("code")) != "200":
            error = str(event.get("message") or event.get("code"))
            continue

        request_id = str(event.get("request_id") or request_id or "") or request_id
        if event.get("usage"):
            usage = event.get("usage")

        output = event.get("output") or {}
        if isinstance(output, dict) and output.get("request_id"):
            request_id = str(output.get("request_id"))

        choices = []
        if isinstance(output, dict):
            choices = output.get("choices") or []
        if not choices and event.get("choices"):
            choices = event.get("choices") or []

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
                stages.append(step_change)

            add_kw = msg.get("additional_kwargs") or {}
            if isinstance(add_kw, dict):
                extra_json = add_kw.get("extra_json")
                docs.extend(_extract_docs(extra_json))

            text = _content_text(msg.get("content"))
            if not text:
                continue
            if step == "generating" or group == "generating":
                reply_parts.append(text)
            elif step == "planning" or group == "planning":
                planning_parts.append(text)

    return {
        "reply": "".join(reply_parts).strip(),
        "planning_text": "".join(planning_parts).strip(),
        "retrieved_docs": docs,
        "request_id": request_id,
        "usage": usage,
        "stages": stages,
        "error": error,
    }


def knowledge_chat_sync(
    query: str,
    *,
    aid: str,
    cfg: BailianConfig | None = None,
    messages: list[dict[str, Any]] | None = None,
    timeout: float = 90,
) -> KnowledgeChatResult | None:
    """同步调用知识问答；仅传用户问题，不附加代码侧 instructions。"""
    c = cfg or load_bailian_config()
    q = (query or "").strip()
    agent_id = (aid or "").strip()
    if not q or not agent_id:
        return None
    if not (c.workspace_id and c.dashscope_api_key):
        logger.warning("knowledge_chat not configured (workspace/dashscope key)")
        return None

    msgs = messages or [{"role": "user", "content": [{"type": "text", "text": q}]}]
    payload = {
        "input": {"messages": msgs},
        "parameters": {"agent_options": {"agent_id": agent_id}},
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {c.dashscope_api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    url = knowledge_chat_url(c)

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
                parsed = parse_knowledge_chat_sse(resp.iter_lines())
    except httpx.TimeoutException as e:
        logger.warning("knowledge_chat timeout aid=%s err=%s", agent_id, e)
        return None
    except Exception as e:
        logger.warning("knowledge_chat failed aid=%s err=%s", agent_id, e)
        return None

    if parsed.get("error"):
        logger.warning("knowledge_chat sse error aid=%s err=%s", agent_id, parsed["error"])
        return None

    reply = parsed.get("reply") or ""
    if not reply:
        logger.warning("knowledge_chat empty reply aid=%s stages=%s", agent_id, parsed.get("stages"))

    return KnowledgeChatResult(
        reply=reply,
        aid=agent_id,
        request_id=parsed.get("request_id"),
        usage=parsed.get("usage"),
        retrieved_docs=parsed.get("retrieved_docs") or [],
        planning_text=parsed.get("planning_text") or "",
        stages=parsed.get("stages") or [],
    )
