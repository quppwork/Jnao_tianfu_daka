"""密码强度校验 — 注册/改密"""

from __future__ import annotations

import re

from fastapi import HTTPException

_WEAK_PASSWORDS = frozenset(
    {
        "123456",
        "12345678",
        "123456789",
        "111111",
        "000000",
        "654321",
        "password",
        "qwerty",
        "abc123",
        "123123",
        "888888",
        "666666",
    }
)


def validate_password_strength(password: str, *, field_label: str = "密码") -> str:
    pwd = (password or "").strip()
    if len(pwd) < 8:
        raise HTTPException(400, f"{field_label}至少8位，且需包含字母和数字")
    if not re.search(r"[A-Za-z]", pwd) or not re.search(r"\d", pwd):
        raise HTTPException(400, f"{field_label}需同时包含字母和数字")
    if pwd.lower() in _WEAK_PASSWORDS:
        raise HTTPException(400, f"{field_label}过于简单，请更换")
    return pwd
