"""ListIndexDocuments — 列出知识库文件概要（不拉全文）。"""

from __future__ import annotations

from typing import Any

from app.core.logger import get_logger
from app.services.bailian.client import create_openapi_client
from app.services.bailian.config import BailianConfig, config_ready_for_retrieve, load_bailian_config

logger = get_logger("bailian.list_documents")


def list_index_documents(
    *,
    index_id: str | None = None,
    cfg: BailianConfig | None = None,
    page_number: int = 1,
    page_size: int = 50,
    document_status: str = "FINISH",
) -> list[dict[str, Any]]:
    """返回 [{name, status, document_id, ...}, ...]。失败返回空列表。"""
    from alibabacloud_bailian20231229 import models as bailian_models
    from alibabacloud_tea_util import models as util_models

    c = cfg or load_bailian_config()
    if not config_ready_for_retrieve(c):
        logger.warning("list_index_documents: retrieve config incomplete")
        return []

    idx = (index_id or c.index_id or "").strip()
    if not idx:
        return []

    client = create_openapi_client(c)
    request = bailian_models.ListIndexDocumentsRequest(
        index_id=idx,
        page_number=max(1, page_number),
        page_size=max(1, min(page_size, 100)),
        document_status=document_status or None,
    )
    runtime = util_models.RuntimeOptions()
    try:
        resp = client.list_index_documents_with_options(
            c.workspace_id, request, {}, runtime
        )
    except Exception as e:
        logger.warning("list_index_documents failed index=%s err=%s", idx, e)
        return []

    body = getattr(resp, "body", None)
    data = getattr(body, "data", None) if body else None
    docs = list(getattr(data, "documents", None) or []) if data else []
    out: list[dict[str, Any]] = []
    for d in docs:
        name = (
            getattr(d, "name", None)
            or getattr(d, "document_name", None)
            or getattr(d, "document_name", None)
            or ""
        )
        # SDK 字段兼容
        if not name and hasattr(d, "to_map"):
            m = d.to_map() or {}
            name = m.get("Name") or m.get("DocumentName") or m.get("name") or ""
        name = str(name).strip()
        if not name:
            continue
        # 去扩展名作 tag 候选
        stem = name.rsplit(".", 1)[0] if "." in name else name
        out.append({
            "name": name,
            "stem": stem.strip(),
            "status": str(getattr(d, "status", None) or getattr(d, "document_status", None) or ""),
            "document_id": str(getattr(d, "id", None) or getattr(d, "document_id", None) or ""),
        })
    return out


def list_all_index_document_stems(
    *,
    index_id: str | None = None,
    cfg: BailianConfig | None = None,
    max_pages: int = 20,
) -> list[str]:
    """分页拉齐已完成索引的文档名（无后缀）。"""
    stems: list[str] = []
    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        batch = list_index_documents(
            index_id=index_id, cfg=cfg, page_number=page, page_size=50
        )
        if not batch:
            break
        for item in batch:
            stem = (item.get("stem") or "").strip()
            if stem and stem not in seen:
                seen.add(stem)
                stems.append(stem)
        if len(batch) < 50:
            break
    return stems
