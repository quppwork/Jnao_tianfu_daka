"""可替换的知识后端接口 — Agent/Pipeline 只依赖本抽象，不绑死百炼。

当前实现：`BailianKnowledgeBackend`（Retrieve 切片 / knowledge_chat 整段答）。
日后私有 RAG：实现同一 Protocol 即可，编排层不用改。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.services.bailian.models import RagResult
from app.services.bailian.knowledge_chat import KnowledgeChatResult


@dataclass
class KnowledgeAnswer:
    """编排层统一消费的知识结果（切片检索或整段问答）。"""

    kind: str  # "chunks" | "chat"
    query: str
    text: str = ""
    sources: list[str] = field(default_factory=list)
    rag: RagResult | None = None
    chat: KnowledgeChatResult | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class KnowledgeBackend(Protocol):
    async def retrieve_chunks(
        self,
        query: str,
        *,
        index_id: str | None = None,
        top_n: int | None = None,
        timeout: float = 20,
    ) -> KnowledgeAnswer | None: ...

    async def answer_chat(
        self,
        query: str,
        *,
        aid: str | None = None,
        timeout: float = 90,
    ) -> KnowledgeAnswer | None: ...


class BailianKnowledgeBackend:
    """阿里云百炼：Retrieve/Search → chunks；应用 knowledge/chat → 整段答。"""

    async def retrieve_chunks(
        self,
        query: str,
        *,
        index_id: str | None = None,
        top_n: int | None = None,
        timeout: float = 20,
    ) -> KnowledgeAnswer | None:
        from app.services.bailian import rag_query

        rag = await rag_query(
            query, index_id=index_id, top_n=top_n, timeout=timeout
        )
        if not rag or not rag.nodes:
            return None
        parts = [n.text for n in rag.nodes if (n.text or "").strip()]
        return KnowledgeAnswer(
            kind="chunks",
            query=query,
            text="\n\n".join(parts),
            sources=list(rag.sources or []),
            rag=rag,
            meta={"mode": rag.mode, "node_count": rag.node_count},
        )

    async def answer_chat(
        self,
        query: str,
        *,
        aid: str | None = None,
        timeout: float = 90,
    ) -> KnowledgeAnswer | None:
        import asyncio

        from app.services.bailian.knowledge_chat import knowledge_chat_sync

        agent_id = (aid or "").strip()
        if not agent_id:
            return None
        try:
            chat = await asyncio.wait_for(
                asyncio.to_thread(
                    knowledge_chat_sync, query, aid=agent_id, timeout=timeout
                ),
                timeout=timeout + 5,
            )
        except Exception:
            return None
        if not chat or not (chat.text or "").strip():
            return None
        return KnowledgeAnswer(
            kind="chat",
            query=query,
            text=(chat.text or "").strip(),
            sources=list(getattr(chat, "sources", None) or []),
            chat=chat,
            meta={"aid": agent_id},
        )


_default_backend: KnowledgeBackend | None = None


def get_knowledge_backend() -> KnowledgeBackend:
    global _default_backend
    if _default_backend is None:
        _default_backend = BailianKnowledgeBackend()
    return _default_backend


def set_knowledge_backend(backend: KnowledgeBackend | None) -> None:
    """测试或灰度时可注入替代实现。"""
    global _default_backend
    _default_backend = backend
