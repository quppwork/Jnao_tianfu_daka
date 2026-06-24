"""阿里云 OSS — 列举对象、生成签名播放 URL"""

from __future__ import annotations

import os
from functools import lru_cache
from urllib.parse import unquote, urlparse

from config.loader import load_settings

DEFAULT_ENDPOINT = "oss-cn-beijing.aliyuncs.com"
DEFAULT_BUCKET = "jnao-talent-ai"
DEFAULT_PREFIX = "yinpin/"


def _oss_cfg() -> dict:
    settings = load_settings().get("oss", {})
    return {
        "access_key_id": settings.get("access_key_id", ""),
        "access_key_secret": settings.get("access_key_secret", ""),
        "bucket": settings.get("bucket", DEFAULT_BUCKET),
        "endpoint": settings.get("endpoint", DEFAULT_ENDPOINT),
        "prefix": settings.get("prefix", DEFAULT_PREFIX),
        "signed_url": settings.get("signed_url", True),
        "sign_expires": int(settings.get("sign_expires", 7200)),
    }


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
    if parsed.netloc != bucket_host and cfg["bucket"] not in parsed.netloc:
        return None
    return unquote(parsed.path.lstrip("/"))


def _bucket_client():
    import oss2

    cfg = _oss_cfg()
    auth = oss2.Auth(cfg["access_key_id"], cfg["access_key_secret"])
    return oss2.Bucket(auth, f"https://{cfg['endpoint']}", cfg["bucket"])


def list_audio_objects(prefix: str | None = None) -> list[dict]:
    """列举 OSS 下 MP3 文件，返回 [{key, size, url, last_modified}]"""
    import oss2

    cfg = _oss_cfg()
    if not is_oss_configured():
        raise RuntimeError("OSS 未配置，请在 backend/.env 填写 OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET")

    use_prefix = prefix if prefix is not None else cfg["prefix"]
    bucket = _bucket_client()
    rows: list[dict] = []
    for obj in oss2.ObjectIterator(bucket, prefix=use_prefix):
        key = obj.key
        if not key.lower().endswith(".mp3"):
            continue
        rows.append(
            {
                "key": key,
                "file_name": key.rsplit("/", 1)[-1],
                "size": obj.size,
                "last_modified": str(obj.last_modified),
                "url": public_url(key),
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


def resolve_play_url(url: str | None) -> str | None:
    """API 返回前解析播放地址（私有桶自动签名）"""
    if not url:
        return None
    cfg = _oss_cfg()
    if not cfg["signed_url"] or not is_oss_configured():
        return url
    key = object_key_from_url(url)
    if key:
        return sign_play_url(url)
    return url
