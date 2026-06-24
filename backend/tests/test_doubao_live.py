"""可选：真实豆包 API 联调（默认跳过）"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("DOUBAO_LIVE_TEST") != "1",
    reason="设置 DOUBAO_LIVE_TEST=1 才跑真实豆包请求",
)


@pytest.mark.asyncio
async def test_live_doubao_chat():
    from app.services.doubao_client import chat_completion, is_configured

    if not is_configured():
        pytest.skip("豆包 API Key 未配置")

    reply = await chat_completion(
        system_prompt="你是助手，用一句话回答",
        user_message="1+1等于几？",
        max_tokens=50,
    )
    assert reply
    assert len(reply) > 0
