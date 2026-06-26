"""学科答疑拍图 — 仅本地存储（不上传 OSS）"""

from __future__ import annotations

import base64
import mimetypes
import uuid
from pathlib import Path

_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "data" / "qa_uploads"
_STORE: dict[str, dict] = {}


def _ensure_dir() -> Path:
    _UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    return _UPLOAD_ROOT


def save_qa_image(child_user_id: int, filename: str, raw: bytes, content_type: str) -> dict:
    image_id = uuid.uuid4().hex
    ext = Path(filename or "img.jpg").suffix or mimetypes.guess_extension(content_type or "") or ".jpg"
    if not ext.startswith("."):
        ext = f".{ext}"
    path = _ensure_dir() / f"{child_user_id}_{image_id}{ext}"
    path.write_bytes(raw)
    url = f"/api/qa/images/{image_id}?user_id={child_user_id}"
    meta = {
        "image_id": image_id,
        "path": str(path),
        "url": url,
        "content_type": content_type or "image/jpeg",
        "child_user_id": child_user_id,
    }
    _STORE[image_id] = meta
    return {"image_id": image_id, "url": url}


def get_qa_image(image_id: str, child_user_id: int) -> dict | None:
    meta = _STORE.get(image_id)
    if not meta or meta["child_user_id"] != child_user_id:
        path = _find_on_disk(image_id, child_user_id)
        if not path:
            return None
        meta = {
            "image_id": image_id,
            "path": str(path),
            "content_type": mimetypes.guess_type(str(path))[0] or "image/jpeg",
            "child_user_id": child_user_id,
        }
        _STORE[image_id] = meta
    return meta


def image_data_url(image_id: str, child_user_id: int) -> str | None:
    meta = get_qa_image(image_id, child_user_id)
    if not meta:
        return None
    path = Path(meta["path"])
    if not path.is_file():
        return None
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    ctype = meta.get("content_type") or "image/jpeg"
    return f"data:{ctype};base64,{b64}"


def _find_on_disk(image_id: str, child_user_id: int) -> Path | None:
    root = _ensure_dir()
    for p in root.glob(f"{child_user_id}_{image_id}.*"):
        return p
    return None
