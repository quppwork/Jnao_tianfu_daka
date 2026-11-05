"""训练视频推送 — 天赋固定视频 + 逐条推送预留接口"""

from __future__ import annotations

import logging

from config.loader import load_settings

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.talent_mapping import TALENT_CODE_TO_TAG

logger = logging.getLogger(__name__)

TALENT_VIDEO_STREAM_PATH = "/api/training/video/talent/stream"

# 各天赋默认训练视频（本地静态或 OSS）；逐条视频推送走 get_item_training_video
DEFAULT_TALENT_VIDEOS: dict[int, dict] = {
    1: {"title": "学者·五者天赋视频", "url": "/static/training_video.mp4"},
    2: {"title": "思者·五者天赋视频", "url": "/static/training_video.mp4"},
    3: {"title": "行者·五者天赋视频", "url": "/static/training_video.mp4"},
    4: {"title": "德者·五者天赋视频", "url": "/static/training_video.mp4"},
    5: {"title": "赢者·五者天赋视频", "url": "/static/training_video.mp4"},
}


def _settings_videos() -> dict[int, dict]:
    raw = load_settings().get("training", {}).get("talent_videos", {})
    out: dict[int, dict] = {}
    for key, val in raw.items():
        try:
            code = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(val, dict) and val.get("url"):
            out[code] = val
    return out


def _find_talent_video_row(session: Session):
    from app.db.models import ContentItem
    from app.services.content_meta import parse_item_meta

    rows = session.scalars(
        select(ContentItem)
        .where(
            ContentItem.content_type == "video",
            ContentItem.status == 1,
        )
        .order_by(ContentItem.lesson_sort, ContentItem.id)
    ).all()
    for row in rows:
        meta = parse_item_meta(row)
        if meta.get("skill") == "五者天赋" and row.play_url:
            return row
    return None


def get_talent_video_raw_url(db: Session | None = None) -> str | None:
    """五者天赋视频原始 play_url（未签名，供 stream 代理）"""
    own_db = False
    session = db
    if session is None:
        from app.db.session import get_session_factory

        session = get_session_factory()()
        own_db = True
    try:
        row = _find_talent_video_row(session)
        if row and row.play_url:
            return row.play_url
    finally:
        if own_db:
            session.close()

    cfg = _settings_videos().get(1) or DEFAULT_TALENT_VIDEOS.get(1) or {}
    url = cfg.get("url", "")
    return url if url.startswith("http") else None


def get_talent_training_video(talent_code: int | None, db: Session | None = None) -> dict:
    """按天赋返回固定训练视频（优先 OSS content_item 五者天赋视频）"""
    from app.db.models import ContentItem

    session = db
    own_db = False
    if session is None:
        from app.db.session import get_session_factory

        session = get_session_factory()()
        own_db = True
    try:
        row = _find_talent_video_row(session)
        if row:
            return {
                "title": row.lesson_title or "五者天赋视频讲解",
                "url": TALENT_VIDEO_STREAM_PATH,
                "talent_code": talent_code,
                "source": "oss_content",
            }
    except Exception as exc:
        logger.warning("查询五者天赋视频失败: %s", exc)
    finally:
        if own_db:
            session.close()

    if not talent_code:
        return {
            "title": "五者天赋视频",
            "url": TALENT_VIDEO_STREAM_PATH,
            "source": "default",
        }
    cfg = _settings_videos().get(talent_code) or DEFAULT_TALENT_VIDEOS.get(talent_code)
    if not cfg:
        tag = TALENT_CODE_TO_TAG.get(talent_code, "")
        cfg = {"title": f"{tag}者·五者天赋视频", "url": "/static/training_video.mp4"}
    url = cfg["url"]
    if url.startswith("http"):
        url = TALENT_VIDEO_STREAM_PATH
    return {
        "title": cfg.get("title", "五者天赋视频"),
        "url": url,
        "talent_code": talent_code,
        "source": "talent_fixed",
    }


def get_item_training_video(content_item_id: int | None, *, video_url: str | None = None) -> dict | None:
    """
    预留：按训练项/内容 ID 推送对应视频。
    Phase 2 实现逐条匹配；当前仅在有 video_url 时返回 stream 代理路径。
    """
    if not content_item_id and not video_url:
        return None
    if video_url:
        return {
            "content_item_id": content_item_id,
            "title": "训练视频",
            "url": TALENT_VIDEO_STREAM_PATH if video_url.startswith("http") else video_url,
            "source": "content_item",
            "status": "available",
        }
    return {
        "content_item_id": content_item_id,
        "title": None,
        "url": None,
        "source": "content_item",
        "status": "not_implemented",
        "message": "逐条视频推送尚未启用，请使用天赋固定视频",
    }
