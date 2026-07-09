"""图形验证码 — 发短信前人机校验（PNG 渲染，答案仅存服务端）"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import random
import secrets
import string

from fastapi import HTTPException

from app.services.auth_challenge_store import (
    challenge_delete,
    challenge_get,
    challenge_get_count,
    challenge_incr,
    challenge_set,
)

CAPTCHA_TTL = 120
CAPTCHA_FAIL_LOCK = 5
CAPTCHA_LOCK_TTL = 900
CAPTCHA_IP_LIMIT = int(os.getenv("CAPTCHA_IP_LIMIT", "15"))
CAPTCHA_IP_WINDOW = 60
_KEY_PREFIX = "auth:captcha:"


def _is_mock() -> bool:
    return os.getenv("AUTH_CHALLENGE_MOCK", "").strip() in ("1", "true", "yes")


def _hash_answer(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


def check_captcha_rate_limit(client_ip: str) -> None:
    ip = (client_ip or "unknown").strip() or "unknown"
    key = f"auth:captcha:ip:{ip}"
    if challenge_get_count(key) >= CAPTCHA_IP_LIMIT:
        raise HTTPException(429, "验证码请求过于频繁，请稍后再试")
    challenge_incr(key, CAPTCHA_IP_WINDOW)


def _make_png(text: str) -> str:
    from PIL import Image, ImageDraw, ImageFont

    width, height = 140, 48
    img = Image.new("RGB", (width, height), (243, 244, 246))
    draw = ImageDraw.Draw(img)

    for _ in range(8):
        draw.line(
            (
                random.randint(0, width),
                random.randint(0, height),
                random.randint(0, width),
                random.randint(0, height),
            ),
            fill=(
                random.randint(120, 200),
                random.randint(120, 200),
                random.randint(120, 200),
            ),
            width=1,
        )
    for _ in range(40):
        draw.point(
            (random.randint(0, width - 1), random.randint(0, height - 1)),
            fill=(
                random.randint(80, 180),
                random.randint(80, 180),
                random.randint(80, 180),
            ),
        )

    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except OSError:
        font = ImageFont.load_default()

    x = 12
    for ch in text:
        y = random.randint(8, 16)
        color = (
            random.randint(20, 100),
            random.randint(20, 100),
            random.randint(20, 100),
        )
        draw.text((x, y), ch, fill=color, font=font)
        x += 28

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def create_captcha(*, client_ip: str = "") -> dict:
    check_captcha_rate_limit(client_ip)

    if _is_mock():
        captcha_id = "mock"
        challenge_set(
            f"{_KEY_PREFIX}{captcha_id}",
            {"answer_hash": _hash_answer("0000"), "fail_count": 0},
            CAPTCHA_TTL,
        )
        return {
            "captcha_id": captcha_id,
            "image_base64": _make_png("0000"),
            "image_format": "png",
            "expires_in": CAPTCHA_TTL,
        }

    text = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    captcha_id = secrets.token_urlsafe(12)
    challenge_set(
        f"{_KEY_PREFIX}{captcha_id}",
        {"answer_hash": _hash_answer(text), "fail_count": 0},
        CAPTCHA_TTL,
    )
    return {
        "captcha_id": captcha_id,
        "image_base64": _make_png(text),
        "image_format": "png",
        "expires_in": CAPTCHA_TTL,
    }


def verify_captcha(captcha_id: str, code: str, *, consume: bool = True) -> None:
    if not captcha_id or not code:
        raise HTTPException(400, "请输入图形验证码")

    lock_key = f"auth:captcha_lock:{captcha_id}"
    if challenge_get(lock_key):
        raise HTTPException(429, "图形验证码错误次数过多，请稍后再试")

    row = challenge_get(f"{_KEY_PREFIX}{captcha_id}")
    if not row:
        raise HTTPException(400, "图形验证码已过期，请刷新")

    if _hash_answer(code) != row.get("answer_hash"):
        fail = int(row.get("fail_count") or 0) + 1
        if fail >= CAPTCHA_FAIL_LOCK:
            challenge_set(lock_key, {"locked": True}, CAPTCHA_LOCK_TTL)
            challenge_delete(f"{_KEY_PREFIX}{captcha_id}")
            raise HTTPException(429, "图形验证码错误次数过多，请稍后再试")
        row["fail_count"] = fail
        challenge_set(f"{_KEY_PREFIX}{captcha_id}", row, CAPTCHA_TTL)
        raise HTTPException(400, "图形验证码错误")

    if consume:
        challenge_delete(f"{_KEY_PREFIX}{captcha_id}")
