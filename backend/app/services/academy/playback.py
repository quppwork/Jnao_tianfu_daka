"""播放地址。与今日修炼共用 media_redirect：

- 有 OSS_CDN_DOMAIN：sector 直接下发 CDN 签名 URL
- 否则：同源 /stream（短签 mt），stream 接口 302 到 OSS（OSS_MEDIA_DIRECT_REDIRECT）
"""

from __future__ import annotations

import zlib

from app.agents.academy.catalog import Episode
from app.services.academy.demo import media_kind
from app.services.oss_client import public_url, sign_cdn_play_url, use_cdn_for_media


def kind_of(episode: Episode) -> str:
    return media_kind(episode.id, episode.oss_key)


def stored_oss_url(episode: Episode) -> str | None:
    """桶内对象的原始 HTTPS URL（未签名），供 stream 回源 / 签名。"""
    key = (episode.oss_key or "").strip()
    if not key:
        return None
    if key.startswith("http"):
        return key
    return public_url(key)


def episode_stream_token_id(episode_id: str) -> int:
    """把剧集 id 稳定映射成 int，复用训练流的 mt 签名。"""
    return zlib.crc32((episode_id or "").encode("utf-8")) & 0x7FFFFFFF


def stream_path(episode_id: str) -> str:
    return f"/api/academy/episodes/{episode_id}/stream"


def play_url(episode: Episode, *, user_id: int | None = None) -> str | None:
    if kind_of(episode) != "oss":
        return None
    # CDN：与训练 plan_view 一致，前端直连加速域
    if use_cdn_for_media():
        raw = stored_oss_url(episode)
        return sign_cdn_play_url(raw) or raw
    # 无 CDN：同源 stream → try_media_redirect 302 OSS
    path = stream_path(episode.id)
    if user_id:
        from app.core.media_stream_token import append_media_stream_token

        path = append_media_stream_token(
            path,
            episode_stream_token_id(episode.id),
            int(user_id),
            "video",
        )
        if "user_id=" not in path:
            sep = "&" if "?" in path else "?"
            path = f"{path}{sep}user_id={int(user_id)}"
    return path


def duration_label(episode: Episode) -> str:
    if episode.duration_label:
        return episode.duration_label
    if kind_of(episode) == "demo":
        return "模拟正片"
    return "正片待上传"
