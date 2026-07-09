"""上传图片校验 — Magic Bytes + Pillow 重编码"""

from __future__ import annotations

import io
import re
from pathlib import Path

from fastapi import HTTPException

MAX_IMAGE_BYTES = 5 * 1024 * 1024
_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def _safe_filename(name: str) -> str:
    base = Path(name or "photo.jpg").name
    if ".." in base or "/" in base or "\\" in base:
        raise HTTPException(400, "文件名不合法")
    if not _SAFE_NAME_RE.match(base):
        raise HTTPException(400, "文件名不合法")
    ext = Path(base).suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(400, "仅支持 JPEG/PNG/WebP 图片")
    return base


def validate_and_normalize_image(filename: str, raw: bytes) -> tuple[bytes, str, str]:
    """返回 (normalized_bytes, content_type, stored_ext)"""
    if not raw:
        raise HTTPException(400, "图片为空")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(400, "图片超过 5MB")

    _safe_filename(filename)

    try:
        from PIL import Image
    except ImportError as e:
        raise HTTPException(503, "图片处理服务未就绪") from e

    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
        img = Image.open(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(400, "无效的图片文件") from e

    fmt = (img.format or "").upper()
    if fmt == "JPEG":
        content_type = "image/jpeg"
        stored_ext = ".jpg"
        out_fmt = "JPEG"
    elif fmt == "PNG":
        content_type = "image/png"
        stored_ext = ".png"
        out_fmt = "PNG"
    elif fmt == "WEBP":
        content_type = "image/webp"
        stored_ext = ".webp"
        out_fmt = "WEBP"
    else:
        raise HTTPException(400, "仅支持 JPEG/PNG/WebP 图片")

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    buf = io.BytesIO()
    save_kwargs: dict = {"optimize": True}
    if out_fmt == "JPEG":
        save_kwargs["quality"] = 85
    img.save(buf, format=out_fmt, **save_kwargs)
    normalized = buf.getvalue()
    if not normalized:
        raise HTTPException(400, "图片处理失败")
    return normalized, content_type, stored_ext
