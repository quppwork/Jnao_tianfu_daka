"""SqlThreadStore — 按 domain 分发到适配器（对照 What Now Memory 单入口）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.memory.adapters.guide import GuideThreadAdapter
from app.memory.adapters.qa import QaThreadAdapter
from app.memory.adapters.report_talent import ReportTalentThreadAdapter
from app.memory.protocols import (
    DOMAIN_GUIDE,
    DOMAIN_PARENT_GUIDE,
    DOMAIN_QA,
    DOMAIN_REPORT_TALENT,
    ThreadMessage,
    ThreadRef,
)


class SqlThreadStore:
    """统一会话存储门面。新板块只加 adapter，不改调用方。"""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._adapters = {
            DOMAIN_REPORT_TALENT: ReportTalentThreadAdapter(db),
            DOMAIN_GUIDE: GuideThreadAdapter(db),
            DOMAIN_PARENT_GUIDE: GuideThreadAdapter(db),
            DOMAIN_QA: QaThreadAdapter(db),
        }

    def _adapter(self, ref: ThreadRef):
        if not ref.domain or not ref.thread_key:
            raise ValueError("ThreadRef.domain / thread_key 不能为空")
        adapter = self._adapters.get(ref.domain)
        if adapter is None:
            raise NotImplementedError(
                f"domain={ref.domain!r} 尚未接入 ThreadStore；"
                f"已支持: {sorted(self._adapters)}"
            )
        return adapter

    def list_messages(self, ref: ThreadRef, *, limit: int = 100) -> list[ThreadMessage]:
        return self._adapter(ref).list_messages(ref, limit=limit)

    def append(
        self,
        ref: ThreadRef,
        *,
        role: str,
        content: str,
        meta: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> ThreadMessage:
        return self._adapter(ref).append(
            ref, role=role, content=content, meta=meta, commit=commit
        )

    def append_pair(
        self,
        ref: ThreadRef,
        *,
        user_content: str,
        assistant_content: str,
        user_meta: dict[str, Any] | None = None,
        assistant_meta: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> tuple[ThreadMessage, ThreadMessage]:
        return self._adapter(ref).append_pair(
            ref,
            user_content=user_content,
            assistant_content=assistant_content,
            user_meta=user_meta,
            assistant_meta=assistant_meta,
            commit=commit,
        )

    def clear(self, ref: ThreadRef, *, commit: bool = True) -> int:
        return self._adapter(ref).clear(ref, commit=commit)


def get_thread_store(db: Session) -> SqlThreadStore:
    return SqlThreadStore(db)
