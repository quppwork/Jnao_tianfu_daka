"""Mock AI 代理 — 无网络依赖，tianfu_rag 不可用时 health 返回 False"""


class AiProxyMock:
    async def check_health(self) -> bool:
        return False
