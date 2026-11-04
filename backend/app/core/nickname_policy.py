"""昵称/姓名：2-20 长度；登录账号另有字符与禁用词规则。"""

from __future__ import annotations

import re

from fastapi import HTTPException

_FORBIDDEN_EXACT = frozenset(
    {
        "admin",
        "administrator",
        "root",
        "system",
        "test",
        "null",
        "undefined",
        "管理员",
        "系统",
        "官方",
        "客服",
        "运营",
        "习近平",
        "共产党",
        "法轮功",
        "习近平总书记",
    }
)

_FORBIDDEN_SUBSTR = (
    re.compile(r"(?i)fuck|shit|bitch|porn|sex|nazi"),
    re.compile(r"习近平|法轮功|六四|台独|藏独|疆独"),
    re.compile(r"(?i)admin|root|system"),
)


def _reject_forbidden(text: str, *, field_label: str) -> None:
    lower = text.lower()
    if lower in _FORBIDDEN_EXACT:
        raise HTTPException(400, f"{field_label}不符合规范，请更换")
    for pat in _FORBIDDEN_SUBSTR:
        if pat.search(text):
            raise HTTPException(400, f"{field_label}含有不允许的内容")


def validate_real_name(name: str, *, field_label: str = "真实姓名") -> str:
    value = (name or "").strip()
    if len(value) < 2 or len(value) > 20:
        raise HTTPException(400, f"{field_label}需为2-20个字符")
    return value


def validate_nickname(
    nickname: str,
    *,
    field_label: str = "昵称",
    prefer_real_name: bool = False,  # 兼容旧调用；现仅校验长度
) -> str:
    _ = prefer_real_name
    value = (nickname or "").strip()
    if len(value) < 2 or len(value) > 20:
        raise HTTPException(400, f"{field_label}需为2-20个字符")
    return value


def validate_login_name(login_name: str) -> str:
    value = (login_name or "").strip()
    if len(value) < 2 or len(value) > 30:
        raise HTTPException(400, "登录账号需为2-30个字符")
    if not re.match(r"^[A-Za-z0-9_\u4e00-\u9fa5]+$", value):
        raise HTTPException(400, "登录账号仅限中英文、数字、下划线")
    _reject_forbidden(value, field_label="登录账号")
    return value
