"""Mock AI 代理 — 无网络依赖，用于 tianfu_rag 不可用时的降级"""

import asyncio
from typing import AsyncIterator


MOCK_RESPONSES = [
    "你好！我是 JNAO AI 助手。",
    "我会通过对话的方式引导你完成天赋测试。",
    "准备好了吗？我们开始吧！",
]


class AiProxyMock:
    async def chat(
        self,
        message: str,
        user_id: str = "mobile_user",
        user_department: str = "",
        history: list[dict] | None = None,
    ) -> dict:
        return {"answer": "AI 服务暂未接入，请稍后再试。", "sources": [], "answer_mode": "general"}

    async def proxy_talent_stream(
        self,
        message: str,
        user_id: str = "mobile_user",
        history: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        for token in MOCK_RESPONSES:
            for char in token:
                yield {"type": "token", "content": char}
                await asyncio.sleep(0.02)
            yield {"type": "token", "content": " "}
        yield {"type": "done", "answer": "".join(MOCK_RESPONSES), "sources": [], "source_refs": []}

    async def check_health(self) -> bool:
        return False

    async def generate_report_summary(
        self,
        test_type: str,
        dimensions: list[dict],
        scores: list[dict],
    ) -> str | None:
        return None  # 用模板摘要

    async def quick_respond(self, question: str, answer: str) -> str:
        return "好的，我们继续下一题～"
