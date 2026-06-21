"""可替换的外部服务接口（Protocol）"""

from typing import Protocol, AsyncIterator


class AiProxy(Protocol):
    """AI 代理接口 — real 和 mock 均需实现"""

    async def chat(
        self,
        message: str,
        user_id: str = "mobile_user",
        user_department: str = "",
        history: list[dict] | None = None,
    ) -> dict:
        """非流式对话 — 返回 {answer, sources, answer_mode}"""
        ...

    async def proxy_talent_stream(
        self,
        message: str,
        user_id: str = "mobile_user",
        history: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        """SSE 事件流（token/done/error）"""
        ...

    async def check_health(self) -> bool:
        """上游 AI 服务是否可用"""
        ...

    async def generate_report_summary(
        self,
        test_type: str,
        dimensions: list[dict],
        scores: list[dict],
    ) -> str | None:
        """AI 增强报告摘要，不可用时返回 None"""
        ...

    async def quick_respond(
        self,
        question: str,
        answer: str,
    ) -> str:
        """每道题后的简短自然回应（15字内），超时/失败则返回兜底文案"""
        ...
