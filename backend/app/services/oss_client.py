"""阿里云 OSS — 只读：列举已有对象、生成签名播放 URL（不向 OSS 写入用户数据）"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal
from urllib.parse import unquote, urlparse

from config.loader import load_settings

DEFAULT_ENDPOINT = "oss-cn-beijing.aliyuncs.com"
DEFAULT_BUCKET = "jnao-talent-ai"
DEFAULT_PREFIX = "yinpin/"

VIDEO_EXTENSIONS = frozenset({".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv"})
AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"})
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


def _oss_cfg() -> dict:
    settings = load_settings().get("oss", {})
    cdn_raw = os.getenv("OSS_CDN_DOMAIN", settings.get("cdn_domain", "")).strip()
    cdn_domain = cdn_raw.replace("https://", "").replace("http://", "").strip("/")
    return {
        "access_key_id": settings.get("access_key_id", ""),
        "access_key_secret": settings.get("access_key_secret", ""),
        "bucket": settings.get("bucket", DEFAULT_BUCKET),
        "endpoint": settings.get("endpoint", DEFAULT_ENDPOINT),
        "prefix": settings.get("prefix", DEFAULT_PREFIX),
        "prefixes": settings.get("prefixes", [settings.get("prefix", DEFAULT_PREFIX)]),
        "signed_url": settings.get("signed_url", True),
        "sign_expires": int(settings.get("sign_expires", 7200)),
        "cdn_domain": cdn_domain,
    }


def oss_origin_host() -> str:
    cfg = _oss_cfg()
    return f"{cfg['bucket']}.{cfg['endpoint']}"


def cdn_domain() -> str:
    return _oss_cfg().get("cdn_domain") or ""


def use_cdn_for_media() -> bool:
    return bool(cdn_domain()) and is_oss_configured()


def is_oss_configured() -> bool:
    cfg = _oss_cfg()
    return bool(cfg["access_key_id"] and cfg["access_key_secret"])


def public_url(key: str) -> str:
    cfg = _oss_cfg()
    key = key.lstrip("/")
    return f"https://{cfg['bucket']}.{cfg['endpoint']}/{key}"


def object_key_from_url(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.netloc:
        return url.lstrip("/")
    cfg = _oss_cfg()
    bucket_host = f"{cfg['bucket']}.{cfg['endpoint']}"
    cdn_host = cfg.get("cdn_domain") or ""
    if parsed.netloc == cdn_host:
        return unquote(parsed.path.lstrip("/"))
    if parsed.netloc != bucket_host and cfg["bucket"] not in parsed.netloc:
        return None
    return unquote(parsed.path.lstrip("/"))


def _bucket_client():
    import oss2

    cfg = _oss_cfg()
    auth = oss2.Auth(cfg["access_key_id"], cfg["access_key_secret"])
    return oss2.Bucket(auth, f"https://{cfg['endpoint']}", cfg["bucket"])


def _all_prefixes() -> list[str]:
    """返回所有配置的 OSS 前缀"""
    cfg = _oss_cfg()
    prefixes = cfg.get("prefixes", [cfg["prefix"]])
    return prefixes if prefixes else [cfg["prefix"]]


def list_audio_objects(prefix: str | None = None) -> list[dict]:
    """列举 OSS 下音频文件，返回 [{key, size, url, last_modified}]"""
    return _list_objects(prefix, "audio")


def list_video_objects(prefix: str | None = None) -> list[dict]:
    """列举 OSS 下视频文件，返回 [{key, size, url, last_modified}]"""
    return _list_objects(prefix, "video")


def list_all_media(prefix: str | None = None) -> list[dict]:
    """列举 OSS 下所有媒体文件（音频+视频，可跨多前缀）"""
    if prefix is not None:
        return _list_objects(prefix, "all")
    # 扫描所有配置的前缀
    all_rows: list[dict] = []
    seen: set[str] = set()
    for p in _all_prefixes():
        for row in _list_objects(p, "all"):
            if row["key"] not in seen:
                seen.add(row["key"])
                all_rows.append(row)
    all_rows.sort(key=lambda r: r["key"])
    return all_rows


def _list_objects(
    prefix: str | None = None,
    media_type: Literal["audio", "video", "all"] = "audio",
) -> list[dict]:
    """列举 OSS 对象，按类型过滤"""
    import oss2

    cfg = _oss_cfg()
    if not is_oss_configured():
        raise RuntimeError(
            "OSS 未配置，请在 backend/.env 填写 "
            "OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET"
        )

    use_prefix = prefix if prefix is not None else cfg["prefix"]
    bucket = _bucket_client()
    rows: list[dict] = []
    for obj in oss2.ObjectIterator(bucket, prefix=use_prefix):
        key = obj.key
        ext = os.path.splitext(key)[1].lower()
        if media_type == "audio" and ext not in AUDIO_EXTENSIONS:
            continue
        if media_type == "video" and ext not in VIDEO_EXTENSIONS:
            continue
        if media_type == "all" and ext not in MEDIA_EXTENSIONS:
            continue
        rows.append(
            {
                "key": key,
                "file_name": key.rsplit("/", 1)[-1],
                "ext": ext,
                "size": obj.size,
                "last_modified": str(obj.last_modified),
                "url": public_url(key),
                "media_type": "video" if ext in VIDEO_EXTENSIONS else "audio",
            }
        )
    rows.sort(key=lambda r: r["key"])
    return rows


def sign_play_url(url: str | None, expires: int | None = None) -> str | None:
    """私有 Bucket：将 OSS URL 转为限时签名地址"""
    if not url or not is_oss_configured():
        return url
    cfg = _oss_cfg()
    if not cfg["signed_url"]:
        return url
    key = object_key_from_url(url)
    if not key:
        return url
    bucket = _bucket_client()
    return bucket.sign_url("GET", key, expires or cfg["sign_expires"])


def sign_cdn_play_url(url: str | None, expires: int | None = None) -> str | None:
    """OSS 签名后将域名替换为 CDN 加速域（需控制台已绑定 OSS 回源 + 私有桶回源）。"""
    signed = sign_play_url(url, expires)
    if not signed:
        return signed
    cdn = cdn_domain()
    if not cdn:
        return signed
    origin = oss_origin_host()
    for scheme in ("https", "http"):
        signed = signed.replace(f"{scheme}://{origin}", f"https://{cdn}")
    return signed


def resolve_play_url(url: str | None) -> str | None:
    """API 返回前解析播放地址（私有桶自动签名；配置 CDN 时走加速域）。"""
    if not url:
        return None
    cfg = _oss_cfg()
    if not cfg["signed_url"] or not is_oss_configured():
        return url
    key = object_key_from_url(url)
    if key:
        if use_cdn_for_media():
            return sign_cdn_play_url(url)
        return sign_play_url(url)
    return url
