"""业务行为日志 — 每条带用户唯一标识 uid，便于线上按人排查。

约定：
- uid：ChildUser.id（学生/家长/管理员账号主键，全站唯一）
- rid：单次 HTTP 请求 ID（中间件生成，响应头 X-Request-Id）
- role：student | parent | admin | -
- action：域.动作，如 auth.login / training.checkin / guide.chat

日志示例：
  biz action=training.checkin uid=42 role=student rid=a1b2c3d4 result=ok ms=128 plan_id=9 item_id=3
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

from app.core.logger import get_logger

logger = get_logger("biz")

_request_id: ContextVar[str] = ContextVar("biz_request_id", default="")
_user_id: ContextVar[int | None] = ContextVar("biz_user_id", default=None)
_user_role: ContextVar[str] = ContextVar("biz_user_role", default="-")


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def get_request_id() -> str:
    return _request_id.get() or "-"


def get_user_id() -> int | None:
    return _user_id.get()


def get_user_role() -> str:
    return _user_role.get() or "-"


def set_request_id(rid: str | None) -> None:
    _request_id.set((rid or "").strip() or new_request_id())


def bind_user(uid: int | None, role: str | None = None) -> None:
    """鉴权成功后绑定当前请求的用户标识。"""
    if uid is not None and int(uid) > 0:
        _user_id.set(int(uid))
    if role:
        _user_role.set(str(role).strip() or "-")


def reset_context() -> None:
    _request_id.set("")
    _user_id.set(None)
    _user_role.set("-")


def _fmt_val(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        return f"{v:.1f}" if v >= 10 else f"{v:.2f}"
    s = str(v).replace("\n", " ").replace("\r", " ").strip()
    if len(s) > 80:
        s = s[:77] + "..."
    if any(c in s for c in (" ", "=", '"')):
        return f'"{s}"'
    return s or "-"


def biz_event(
    action: str,
    *,
    result: str = "ok",
    ms: float | None = None,
    uid: int | None = None,
    role: str | None = None,
    level: str = "info",
    **fields: Any,
) -> None:
    """写一条行为日志；uid/role 默认取请求上下文。"""
    user = uid if uid is not None else get_user_id()
    user_role = role if role is not None else get_user_role()
    parts = [
        f"action={_fmt_val(action)}",
        f"uid={_fmt_val(user if user is not None else '-')}",
        f"role={_fmt_val(user_role)}",
        f"rid={_fmt_val(get_request_id())}",
        f"result={_fmt_val(result)}",
    ]
    if ms is not None:
        parts.append(f"ms={_fmt_val(ms)}")
    for k, v in fields.items():
        if v is None or v == "":
            continue
        safe_k = str(k).replace(" ", "_")
        parts.append(f"{safe_k}={_fmt_val(v)}")
    msg = "biz " + " ".join(parts)
    log_fn = getattr(logger, level if level in ("debug", "info", "warning", "error") else "info")
    log_fn(msg)


@contextmanager
def biz_timer(action: str, **fields: Any) -> Iterator[dict[str, Any]]:
    """with biz_timer('training.checkin', plan_id=1) as ctx: ...; ctx['result']='fail'"""
    t0 = time.perf_counter()
    ctx: dict[str, Any] = {"result": "ok", "fields": dict(fields)}
    try:
        yield ctx
    except Exception as e:
        ctx["result"] = ctx.get("result") or "error"
        ctx["fields"]["err"] = type(e).__name__
        biz_event(
            action,
            result=str(ctx["result"]),
            ms=(time.perf_counter() - t0) * 1000,
            level="warning",
            **ctx["fields"],
        )
        raise
    else:
        biz_event(
            action,
            result=str(ctx.get("result") or "ok"),
            ms=(time.perf_counter() - t0) * 1000,
            level=str(ctx.get("level") or "info"),
            **ctx.get("fields") or {},
        )


# 需要写行为摘要的路径前缀（其余仅保留 -->/<-- 或静默）
BIZ_PATH_PREFIXES = (
    "/api/auth/",
    "/api/training/",
    "/api/guide/",
    "/api/qa/",
    "/api/parent/",
    "/api/talent/",
    "/api/growth/",
    "/api/admin/",
    "/api/user/",
)

# 高噪声只记失败
QUIET_PATH_SUFFIXES = (
    "/stream",
    "/ping",
    "/health",
)


def should_log_http(path: str, status: int) -> bool:
    if any(path.endswith(s) or f"{s}?" in path for s in ("/ping", "/health")):
        return status >= 400
    if path.endswith("/stream") or "/images/" in path:
        return status >= 400
    return any(path.startswith(p) for p in BIZ_PATH_PREFIXES)
