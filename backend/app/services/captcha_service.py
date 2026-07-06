"""图形验证码 — 发短信前人机校验"""

from __future__ import annotations

import base64
import hashlib
import os
import random
import secrets
import string

from fastapi import HTTPException

from app.services.auth_challenge_store import challenge_delete, challenge_get, challenge_set

CAPTCHA_TTL = 120
CAPTCHA_FAIL_LOCK = 5
CAPTCHA_LOCK_TTL = 900
_KEY_PREFIX = "auth:captcha:"


def _is_mock() -> bool:
    return os.getenv("AUTH_CHALLENGE_MOCK", "").strip() in ("1", "true", "yes")


def _hash_answer(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


def _make_svg(text: str) -> str:
  lines = []
  for i, ch in enumerate(text):
    x = 18 + i * 24 + random.randint(-3, 3)
    y = 26 + random.randint(-4, 4)
    rot = random.randint(-25, 25)
    color = f"rgb({random.randint(30,120)},{random.randint(30,120)},{random.randint(30,120)})"
    lines.append(
      f'<text x="{x}" y="{y}" fill="{color}" font-size="22" font-family="Arial,sans-serif" '
      f'font-weight="700" transform="rotate({rot} {x} {y})">{ch}</text>'
    )
  noise = "".join(
    f'<line x1="{random.randint(0,120)}" y1="{random.randint(0,40)}" '
    f'x2="{random.randint(0,120)}" y2="{random.randint(0,40)}" stroke="#999" stroke-width="1" opacity="0.5"/>'
    for _ in range(6)
  )
  svg = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40" viewBox="0 0 120 40">'
    f'<rect width="120" height="40" fill="#f3f4f6" rx="4"/>{noise}{"".join(lines)}</svg>'
  )
  return base64.b64encode(svg.encode("utf-8")).decode("ascii")


def create_captcha() -> dict:
    if _is_mock():
        captcha_id = "mock"
        challenge_set(
            f"{_KEY_PREFIX}{captcha_id}",
            {"answer_hash": _hash_answer("0000"), "fail_count": 0},
            CAPTCHA_TTL,
        )
        return {
            "captcha_id": captcha_id,
            "image_base64": _make_svg("0000"),
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
        "image_base64": _make_svg(text),
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
