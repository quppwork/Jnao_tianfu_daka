"""训练音视频流短期签名 — 供 <video>/<audio> src 使用（无法带 Header/Cookie 时兜底）"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time


def _secret_bytes() -> bytes:
    raw = (os.getenv("MEDIA_STREAM_TOKEN_SECRET") or os.getenv("ADMIN_PASSWORD") or "").strip()
    if not raw:
        raw = "dev-media-stream-secret"
    return raw.encode()


def make_media_stream_token(item_id: int, user_id: int, media: str, *, ttl_sec: int = 7200) -> str:
    exp = int(time.time()) + max(60, ttl_sec)
    msg = f"{item_id}:{user_id}:{media}:{exp}"
    sig = hmac.new(_secret_bytes(), msg.encode(), hashlib.sha256).hexdigest()[:32]
    raw = f"{exp}.{sig}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def verify_media_stream_token(token: str, item_id: int, user_id: int, media: str) -> bool:
    if not token or not user_id:
        return False
    try:
        pad = "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(token + pad).decode()
        exp_s, sig = decoded.split(".", 1)
        exp = int(exp_s)
        if exp < time.time():
            return False
        msg = f"{item_id}:{user_id}:{media}:{exp}"
        expect = hmac.new(_secret_bytes(), msg.encode(), hashlib.sha256).hexdigest()[:32]
        return hmac.compare_digest(sig, expect)
    except Exception:
        return False


def append_media_stream_token(url: str, item_id: int, user_id: int, media: str) -> str:
    tok = make_media_stream_token(item_id, user_id, media)
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}mt={tok}"
