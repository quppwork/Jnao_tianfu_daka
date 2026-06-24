"""健康检查 API"""

from fastapi import APIRouter
from sqlalchemy import text

from app.api import ai_proxy
from app.db.session import get_session_factory
from config import load_integration, load_settings

router = APIRouter(tags=["health"])


@router.get("/api/ping")
def ping():
    """轻量存活探测 — 供启动脚本使用，不探测上游"""
    return {"ok": True}


def _check_database() -> dict:
    try:
        session = get_session_factory()()
        try:
            session.execute(text("SELECT 1"))
            return {"status": "live", "connected": True}
        finally:
            session.close()
    except Exception as e:
        return {"status": "error", "connected": False, "error": str(e)[:120]}


@router.get("/api/health")
async def health():
    """返回各服务接入状态"""
    import asyncio
    import os

    settings = load_settings()
    upstream_url = settings["upstream"]["tianfu_rag"]["url"]
    if os.getenv("TIANFU_RAG_MOCK", "") == "1":
        upstream_ok = False
    else:
        try:
            upstream_ok = await asyncio.wait_for(ai_proxy.check_health(), timeout=1.0)
        except (asyncio.TimeoutError, Exception):
            upstream_ok = False
    integration = load_integration()
    db_ok = _check_database()

    integrations = {}
    for key, entry in integration["endpoints"].items():
        entry_dict = dict(entry)
        if key in ("talent_submit", "talent_result"):
            entry_dict["status"] = "live"
        elif key == "talent_stream":
            entry_dict["status"] = "live" if upstream_ok else "mock"
        elif key == "tianfu_rag":
            entry_dict["status"] = "live" if upstream_ok else "pending"
        integrations[key] = entry_dict

    integrations["tianfu_rag"] = {
        "status": "live" if upstream_ok else "pending",
        "description": "AI 流式对话（tianfu_rag /chat/stream）",
        "url": upstream_url,
        "connected": upstream_ok,
    }
    integrations["mysql"] = {
        "status": "live" if db_ok["connected"] else "error",
        "description": "业务数据库 jnao_daka",
        **db_ok,
    }

    from app.services.doubao_client import is_configured
    settings = load_settings()
    doubao_cfg = settings.get("doubao", {})
    integrations["doubao"] = {
        "status": "live" if is_configured() else "pending",
        "description": "豆包 Ark 对话（guide/chat/qa/训练报告）",
        "model": doubao_cfg.get("model"),
        "connected": is_configured(),
    }

    overall = "ok" if db_ok["connected"] else "degraded"
    return {
        "status": overall,
        "version": "0.3.0",
        "integrations": integrations,
    }
