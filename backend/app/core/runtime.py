"""进程级运行时信息 — boot_id、维护模式、发版标志。"""

from __future__ import annotations

import os
import uuid

from app.core.security import is_production

_BOOT_ID: str | None = None
_REDIS_WARNED = False


def init_runtime() -> str:
    """应用启动时调用，生成本进程 boot_id。"""
    global _BOOT_ID
    _BOOT_ID = uuid.uuid4().hex
    return _BOOT_ID


def get_boot_id() -> str:
    return _BOOT_ID or "uninitialized"


def should_force_relogin_on_boot() -> bool:
    """开发默认开启：后端重启后前端清登录态。生产默认关闭。"""
    default = "0" if is_production() else "1"
    return os.getenv("JNAO_DEV_FORCE_RELOGIN", default).strip() == "1"


def is_maintenance() -> bool:
    """部署窗口：前端展示维护页，业务请求仍可按需拦截。"""
    return os.getenv("JNAO_MAINTENANCE", "0").strip() == "1"


def maintenance_message() -> str:
    return (
        os.getenv("JNAO_MAINTENANCE_MSG", "").strip()
        or "系统升级中，请稍后再试"
    )


def should_force_logout() -> bool:
    """不兼容发版时置 1：前端清本地登录（与 boot 重登独立）。"""
    return os.getenv("JNAO_FORCE_LOGOUT", "0").strip() == "1"


def warn_redis_once(logger) -> None:
    """REDIS_URL 缺失只提示一次，避免 --reload 刷屏。"""
    global _REDIS_WARNED
    if _REDIS_WARNED:
        return
    if os.getenv("REDIS_URL", "").strip():
        return
    if os.getenv("JNAO_SKIP_ADMIN_SEED") == "1":
        return
    _REDIS_WARNED = True
    logger.warning(
        "未配置 REDIS_URL：多 worker 下限流/OAuth 状态不共享（B16）"
    )


def runtime_flags() -> dict:
    """ping / meta/version 共用的运行时标志。"""
    return {
        "boot_id": get_boot_id(),
        "force_relogin_on_boot": should_force_relogin_on_boot(),
        "maintenance": is_maintenance(),
        "maintenance_message": maintenance_message() if is_maintenance() else "",
        "force_logout": should_force_logout(),
    }


def ping_payload() -> dict:
    return {"ok": not is_maintenance(), **runtime_flags()}
