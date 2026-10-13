"""工具结果 Evidence — 结果可不可信。

create_evidence：对工具产出做内容哈希并写入账本。
默认 MemoryLedger（进程内）；后续可换 SQL/对象存储实现同一接口。
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


def content_hash(payload: Any) -> str:
    """稳定内容哈希（sha256 hex）。"""
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Evidence:
    id: str
    tool: str
    profile: str
    ok: bool
    content_sha256: str
    created_at: float
    meta: dict[str, Any] = field(default_factory=dict)
    # 可选：截断后的结果摘要，便于审计；完整正文不强制进账本
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceLedger(Protocol):
    def append(self, ev: Evidence) -> None: ...

    def get(self, evidence_id: str) -> Evidence | None: ...

    def list_recent(self, *, limit: int = 50) -> list[Evidence]: ...


class MemoryEvidenceLedger:
    """进程内账本 — 框架默认；测试与单机可用。"""

    def __init__(self, *, max_entries: int = 2000) -> None:
        self._max = max(100, max_entries)
        self._by_id: dict[str, Evidence] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def append(self, ev: Evidence) -> None:
        with self._lock:
            self._by_id[ev.id] = ev
            self._order.append(ev.id)
            while len(self._order) > self._max:
                old = self._order.pop(0)
                self._by_id.pop(old, None)

    def get(self, evidence_id: str) -> Evidence | None:
        with self._lock:
            return self._by_id.get(evidence_id)

    def list_recent(self, *, limit: int = 50) -> list[Evidence]:
        with self._lock:
            ids = self._order[-max(1, limit) :]
            return [self._by_id[i] for i in reversed(ids) if i in self._by_id]

    def clear(self) -> None:
        with self._lock:
            self._by_id.clear()
            self._order.clear()


_LEDGER: EvidenceLedger = MemoryEvidenceLedger()


def get_ledger() -> EvidenceLedger:
    return _LEDGER


def set_ledger(ledger: EvidenceLedger) -> None:
    """替换账本实现（测试 / SQL 落库）。"""
    global _LEDGER
    _LEDGER = ledger


def create_evidence(
    *,
    tool: str,
    payload: Any,
    ok: bool = True,
    profile: str = "",
    meta: dict[str, Any] | None = None,
    summary: str = "",
    ledger: EvidenceLedger | None = None,
) -> Evidence:
    """对工具结果建 Evidence 并写入账本。"""
    digest = content_hash(payload)
    body = payload
    if summary:
        briefly = summary
    elif isinstance(body, dict):
        briefly = json.dumps(body, ensure_ascii=False, default=str)[:240]
    else:
        briefly = str(body)[:240]
    ev = Evidence(
        id=uuid.uuid4().hex,
        tool=tool,
        profile=profile or "",
        ok=ok,
        content_sha256=digest,
        created_at=time.time(),
        meta=dict(meta or {}),
        summary=briefly,
    )
    (ledger or get_ledger()).append(ev)
    return ev


def verify_evidence(ev: Evidence, payload: Any) -> bool:
    """核对内容是否仍匹配账本哈希。"""
    return content_hash(payload) == ev.content_sha256
