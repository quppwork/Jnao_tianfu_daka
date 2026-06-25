"""训练视频推送 — 天赋固定视频 + 逐条推送预留接口"""

from __future__ import annotations

from config.loader import load_settings

from app.core.talent_mapping import TALENT_CODE_TO_TAG
from app.services.oss_client import resolve_play_url

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


def get_talent_training_video(talent_code: int | None) -> dict:
    """按天赋返回固定训练视频（训练 A 视频步骤）"""
    if not talent_code:
        return {"title": "五者天赋视频", "url": "/static/training_video.mp4", "source": "default"}
    cfg = _settings_videos().get(talent_code) or DEFAULT_TALENT_VIDEOS.get(talent_code)
    if not cfg:
        tag = TALENT_CODE_TO_TAG.get(talent_code, "")
        cfg = {"title": f"{tag}者·五者天赋视频", "url": "/static/training_video.mp4"}
    url = resolve_play_url(cfg["url"]) if cfg["url"].startswith("http") else cfg["url"]
    return {
        "title": cfg.get("title", "五者天赋视频"),
        "url": url,
        "talent_code": talent_code,
        "source": "talent_fixed",
    }


def get_item_training_video(content_item_id: int | None, *, video_url: str | None = None) -> dict | None:
    """
    预留：按训练项/内容 ID 推送对应视频。
    Phase 2 实现逐条匹配；当前仅在有 video_url 时返回。
    """
    if not content_item_id and not video_url:
        return None
    if video_url:
        return {
            "content_item_id": content_item_id,
            "title": "训练视频",
            "url": resolve_play_url(video_url),
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
