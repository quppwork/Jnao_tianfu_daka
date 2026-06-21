"""健康检查 API"""

from fastapi import APIRouter

from app.api import ai_proxy
from config import load_settings, load_integration

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health():
    """返回各服务接入状态"""
    settings = load_settings()
    upstream_url = settings["upstream"]["tianfu_rag"]["url"]
    upstream_ok = await ai_proxy.check_health()
    integration = load_integration()

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

    # 注入 tianfu_rag 自身状态（不在 YAML 中定义）
    integrations["tianfu_rag"] = {
        "status": "live" if upstream_ok else "pending",
        "description": "AI 流式对话（tianfu_rag /chat/stream）",
        "url": upstream_url,
        "connected": upstream_ok,
    }

    return {
        "status": "ok",
        "version": "0.2.0",
        "integrations": integrations,
    }
