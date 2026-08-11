"""训练/OSS 媒体播放 — 鉴权后 302 直链（OSS 或 CDN），减轻 VPS 代理带宽"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from fastapi.responses import RedirectResponse

from app.services.oss_client import (
    is_oss_configured,
    object_key_from_url,
    sign_cdn_play_url,
    sign_play_url,
    use_cdn_for_media,
)


def oss_media_direct_redirect_enabled() -> bool:
    raw = os.getenv("OSS_MEDIA_DIRECT_REDIRECT", "1").strip().lower()
    return raw in ("1", "true", "yes", "on")


def oss_media_same_origin_cache_enabled() -> bool:
    raw = os.getenv("OSS_MEDIA_SAME_ORIGIN_CACHE", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def build_same_origin_oss_url(signed_oss_url: str) -> str:
    """将 OSS 签名 URL 转为同域 /api/media/oss/ 路径，供 Nginx 磁盘缓存回源 OSS。"""
    key = object_key_from_url(signed_oss_url)
    if not key:
        return signed_oss_url
    site = (os.getenv("SITE_DOMAIN") or "").strip().rstrip("/")
    if not site:
        return signed_oss_url
    query = urlparse(signed_oss_url).query
    suffix = f"?{query}" if query else ""
    return f"{site}/api/media/oss/{key}{suffix}"


def try_media_redirect(stored_url: str | None) -> RedirectResponse | None:
    """鉴权通过后调用：CDN / OSS 直链 / 同域缓存路径，否则返回 None 走 Python 代理。"""
    if not stored_url or stored_url.startswith("/static/"):
        return None
    if not is_oss_configured():
        return None

    target: str | None = None
    if use_cdn_for_media():
        target = sign_cdn_play_url(stored_url)
    elif oss_media_direct_redirect_enabled():
        target = sign_play_url(stored_url)
        if target and oss_media_same_origin_cache_enabled():
            target = build_same_origin_oss_url(target)

    if not target:
        return None
    return RedirectResponse(target, status_code=302)
