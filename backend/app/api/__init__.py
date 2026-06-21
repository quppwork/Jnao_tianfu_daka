"""API 层 — 解析 AI 代理单例（real 或 mock）"""

import os

from app.services.interfaces import AiProxy


def _resolve_ai_proxy() -> AiProxy:
    if os.getenv("TIANFU_RAG_MOCK", "") == "1":
        from app.mock.ai_proxy_mock import AiProxyMock
        return AiProxyMock()
    from app.services.ai_proxy_real import AiProxyReal
    return AiProxyReal()


ai_proxy: AiProxy = _resolve_ai_proxy()
