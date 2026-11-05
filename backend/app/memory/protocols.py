"""会话存储契约 — 无 I/O，仅类型与协议。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


# 与 model_cost.AgentFeature / harness profile 对齐的 domain 名
DOMAIN_GUIDE = "guide"
DOMAIN_PARENT_GUIDE = "parent_guide"
DOMAIN_QA = "qa"
DOMAIN_REPORT_TALENT = "report_talent"
DOMAIN_CONSULT = "consult"
DOMAIN_ACADEMY = "academy"
DOMAIN_SOLVE = "solve"

KNOWN_DOMAINS = frozenset({
    DOMAIN_GUIDE,
    DOMAIN_PARENT_GUIDE,
    DOMAIN_QA,
    DOMAIN_REPORT_TALENT,
    DOMAIN_CONSULT,
    DOMAIN_ACADEMY,
    DOMAIN_SOLVE,
})


@dataclass(frozen=True)
class ThreadRef:
    """一条会话线程的定位。

    thread_key：
    - guide / qa：session_id
    - report_talent：assessment_id
    - academy：episode_id
    - consult：conversation_id
    """

    domain: str
    owner_user_id: int
    thread_key: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "domain", (self.domain or "").strip())
        object.__setattr__(self, "thread_key", str(self.thread_key or "").strip())


@dataclass(frozen=True)
class ThreadMessage:
    id: int | str | None
    role: str
    content: str
    created_at: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class ThreadStore(Protocol):
    def list_messages(
        self,
        ref: ThreadRef,
        *,
        limit: int = 100,
    ) -> list[ThreadMessage]: ...

    def append(
        self,
        ref: ThreadRef,
        *,
        role: str,
        content: str,
        meta: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> ThreadMessage: ...

    def append_pair(
        self,
        ref: ThreadRef,
        *,
        user_content: str,
        assistant_content: str,
        user_meta: dict[str, Any] | None = None,
        assistant_meta: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> tuple[ThreadMessage, ThreadMessage]: ...

    def clear(self, ref: ThreadRef, *, commit: bool = True) -> int: ...
