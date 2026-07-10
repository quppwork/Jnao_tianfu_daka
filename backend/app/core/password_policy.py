"""密码强度校验 — 注册/改密/创建账号"""

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
        "abc12345",
        "123123",
        "888888",
        "666666",
        "password1",
        "qwerty123",
    }
)

_PASSWORD_HINT = "密码需8-32位，且同时包含大写字母、小写字母和数字"


def password_meets_policy(password: str) -> bool:
    pwd = (password or "").strip()
    if len(pwd) < 8 or len(pwd) > 32:
        return False
    if not re.search(r"[a-z]", pwd):
        return False
    if not re.search(r"[A-Z]", pwd):
        return False
    if not re.search(r"\d", pwd):
        return False
    if pwd.lower() in _WEAK_PASSWORDS:
        return False
    return True


def validate_password_strength(password: str, *, field_label: str = "密码") -> str:
    pwd = (password or "").strip()
    if not password_meets_policy(pwd):
        raise HTTPException(400, f"{field_label}{_PASSWORD_HINT}")
    return pwd

