"""真实 AI 代理 — 仅保留 tianfu_rag 健康探测（对话已迁移至豆包）"""

import httpx

from config import load_settings


class AiProxyReal:
    async def check_health(self) -> bool:
        settings = load_settings()
        url = f"{settings['upstream']['tianfu_rag']['url']}/health"
        timeout = settings["upstream"]["tianfu_rag"]["health_timeout"]
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url)
                return resp.status_code == 200
        except Exception:
            return False
