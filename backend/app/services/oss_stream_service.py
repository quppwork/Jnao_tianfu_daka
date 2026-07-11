"""OSS 媒体流代理 — 后端鉴权 + 按需签名，避免前端直链过期/CORS"""

from __future__ import annotations

import os
import re
from typing import Iterator

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.services.oss_client import _bucket_client, is_oss_configured, object_key_from_url

_RANGE_RE = re.compile(r"bytes=(\d+)-(\d*)")

_EXT_CONTENT_TYPE = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".aac": "audio/aac",
}


def _content_type_for_key(key: str) -> str:
    ext = os.path.splitext(key)[1].lower()
    return _EXT_CONTENT_TYPE.get(ext, "application/octet-stream")


def _parse_byte_range(range_header: str | None) -> tuple[int, int] | None:
    if not range_header:
        return None
    m = _RANGE_RE.match(range_header.strip())
    if not m:
        return None
    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else None
    if end is not None and end < start:
        return None
    if end is None:
        return (start, -1)
    return (start, end)


def stream_oss_media(stored_url: str | None, *, range_header: str | None = None) -> StreamingResponse:
    """从 OSS 读取对象并流式返回（支持 Range，供 video/audio 播放）。"""
    if not stored_url:
        raise HTTPException(404, "媒体资源未找到")
    if not is_oss_configured():
        raise HTTPException(503, "OSS 未配置")

    key = object_key_from_url(stored_url)
    if not key:
        raise HTTPException(404, "媒体资源未找到")

    byte_range = _parse_byte_range(range_header)
    bucket = _bucket_client()
    try:
        result = bucket.get_object(key, byte_range=byte_range)
    except Exception as e:
        err = str(e)
        if "NoSuchKey" in err or "404" in err:
            raise HTTPException(404, "OSS 对象不存在") from e
        raise HTTPException(502, f"OSS 读取失败: {e}") from e

    content_type = (
        (result.headers or {}).get("Content-Type")
        or _content_type_for_key(key)
    )
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": "inline",
        "Content-Type": content_type,
    }
    status_code = 200
    resp_headers = result.headers or {}
    if resp_headers.get("Content-Length"):
        headers["Content-Length"] = resp_headers["Content-Length"]
    if resp_headers.get("Content-Range"):
        headers["Content-Range"] = resp_headers["Content-Range"]
        status_code = 206

    def generate() -> Iterator[bytes]:
        try:
            while True:
                chunk = result.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            result.close()

    return StreamingResponse(generate(), status_code=status_code, headers=headers)


def training_item_stream_path(item_id: int, media: str) -> str:
    return f"/api/training/items/{item_id}/stream?media={media}"
