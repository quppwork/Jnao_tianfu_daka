"""学科答疑 RAG 路由 — 兼容旧接口，内部委托 qa_kb_router。"""

from __future__ import annotations

from app.services.qa_kb_router import QaKbPath, resolve_qa_kb_path


def should_use_rag(
    message: str,
    *,
    subject: str | None = None,
    has_image: bool = False,
    use_rag: bool | None = None,
) -> bool:
    return (
        resolve_qa_kb_path(
            message,
            subject=subject,
            has_image=has_image,
            use_rag=use_rag,
        )
        is not QaKbPath.NONE
    )
