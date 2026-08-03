"""可替换的外部服务接口（Protocol）"""

from typing import Protocol


class AiProxy(Protocol):
    """上游 tianfu_rag 健康探测 — Guide/QA/训练 AI 已改豆包，此处仅 health 使用。"""

    async def check_health(self) -> bool:
        """上游 RAG 服务是否可用"""
        ...
