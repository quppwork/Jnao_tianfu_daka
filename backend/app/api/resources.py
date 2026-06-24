"""资源库查询（只读）"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.db.models import ContentItem
from app.services.oss_client import is_oss_configured, list_audio_objects, resolve_play_url

router = APIRouter(prefix="/api/resources", tags=["resources"])


@router.get("/oss/list")
def oss_audio_list(prefix: str | None = Query(None)):
    """列举 OSS yinpin/ 目录下已上传的 MP3（需配置 AccessKey）"""
    if not is_oss_configured():
        raise HTTPException(503, "OSS 未配置，请在 backend/.env 填写 OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET")
    try:
        items = list_audio_objects(prefix)
    except Exception as e:
        raise HTTPException(502, f"OSS 列举失败: {e}") from e
    return {"total": len(items), "items": items}


@router.get("/list")
def list_resources(
    db: Session = Depends(get_db),
    talent_code: int | None = Query(None),
    content_type: str | None = Query(None),
):
    stmt = select(ContentItem).where(ContentItem.status == 1)
    if talent_code is not None:
        stmt = stmt.where(ContentItem.talent_code == talent_code)
    if content_type:
        stmt = stmt.where(ContentItem.content_type == content_type)
    stmt = stmt.order_by(ContentItem.talent_code, ContentItem.lesson_sort, ContentItem.id)
    rows = db.scalars(stmt).all()
    return {
        "total": len(rows),
        "items": [
            {
                "id": r.id,
                "talent_code": r.talent_code,
                "talent_tag": r.talent_tag,
                "lesson_title": r.lesson_title,
                "lesson_sort": r.lesson_sort,
                "play_url": resolve_play_url(r.play_url),
                "content_type": r.content_type,
            }
            for r in rows
        ],
    }


@router.get("/{resource_id}")
def get_resource(resource_id: int, db: Session = Depends(get_db)):
    row = db.get(ContentItem, resource_id)
    if not row:
        raise HTTPException(404, "资源不存在")
    return {
        "id": row.id,
        "talent_code": row.talent_code,
        "talent_tag": row.talent_tag,
        "lesson_title": row.lesson_title,
        "lesson_sort": row.lesson_sort,
        "play_url": resolve_play_url(row.play_url),
        "video_url": row.video_url,
        "content_type": row.content_type,
        "duration_min": row.duration_min,
        "instructions": row.instructions,
    }
