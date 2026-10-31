"""Evidence SQL 账本 — 实现 EvidenceLedger，启动时可选挂载。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.harness.evidence import Evidence, EvidenceLedger

logger = logging.getLogger("jnao.harness.evidence")


class SqlEvidenceLedger:
    """落库 harness_evidence；失败时降级只打日志不抛。"""

    def append(self, ev: Evidence) -> None:
        try:
            from app.db.models import HarnessEvidenceRow
            from app.db.session import get_session_factory

            db = get_session_factory()()
            try:
                row = HarnessEvidenceRow(
                    id=ev.id,
                    tool=ev.tool,
                    profile=ev.profile or "",
                    ok=1 if ev.ok else 0,
                    content_sha256=ev.content_sha256,
                    summary=(ev.summary or "")[:2000],
                    meta_json=dict(ev.meta or {}),
                    created_at=datetime.fromtimestamp(ev.created_at)
                    if ev.created_at
                    else datetime.now(),
                )
                db.merge(row)
                db.commit()
            finally:
                db.close()
        except Exception:
            logger.exception("sql evidence append failed id=%s", ev.id)

    def get(self, evidence_id: str) -> Evidence | None:
        try:
            from app.db.models import HarnessEvidenceRow
            from app.db.session import get_session_factory

            db = get_session_factory()()
            try:
                row = db.get(HarnessEvidenceRow, evidence_id)
                if not row:
                    return None
                return Evidence(
                    id=row.id,
                    tool=row.tool,
                    profile=row.profile or "",
                    ok=bool(row.ok),
                    content_sha256=row.content_sha256,
                    created_at=row.created_at.timestamp() if row.created_at else 0.0,
                    meta=dict(row.meta_json or {}),
                    summary=row.summary or "",
                )
            finally:
                db.close()
        except Exception:
            logger.exception("sql evidence get failed id=%s", evidence_id)
            return None

    def list_recent(self, *, limit: int = 50) -> list[Evidence]:
        try:
            from sqlalchemy import select

            from app.db.models import HarnessEvidenceRow
            from app.db.session import get_session_factory

            db = get_session_factory()()
            try:
                rows = list(
                    db.scalars(
                        select(HarnessEvidenceRow)
                        .order_by(HarnessEvidenceRow.created_at.desc())
                        .limit(max(1, limit))
                    ).all()
                )
                out: list[Evidence] = []
                for row in rows:
                    out.append(
                        Evidence(
                            id=row.id,
                            tool=row.tool,
                            profile=row.profile or "",
                            ok=bool(row.ok),
                            content_sha256=row.content_sha256,
                            created_at=row.created_at.timestamp() if row.created_at else 0.0,
                            meta=dict(row.meta_json or {}),
                            summary=row.summary or "",
                        )
                    )
                return out
            finally:
                db.close()
        except Exception:
            logger.exception("sql evidence list failed")
            return []


def install_sql_evidence_ledger() -> EvidenceLedger:
    """挂到全局 ledger（生产默认；测试可 set_ledger 覆盖）。"""
    from app.harness.evidence import set_ledger

    ledger: EvidenceLedger = SqlEvidenceLedger()
    set_ledger(ledger)
    return ledger
