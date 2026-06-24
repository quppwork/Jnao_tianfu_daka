"""豆包客户端单元测试"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import doubao_client


class TestDoubaoClient:
    def test_is_configured_false_when_empty(self):
        with patch("app.services.doubao_client.load_settings", return_value={"doubao": {"api_key": ""}}):
            assert doubao_client.is_configured() is False

    def test_is_configured_true_with_key(self):
        with patch(
            "app.services.doubao_client.load_settings",
            return_value={"doubao": {"api_key": "ark-real-key"}},
        ):
            assert doubao_client.is_configured() is True

    def test_build_messages_with_history(self):
        msgs = doubao_client._build_messages(
            "system",
            "新问题",
            [{"role": "user", "content": "旧问题"}, {"role": "assistant", "content": "旧回答"}],
        )
        assert msgs[0]["role"] == "system"
        assert msgs[-1]["content"] == "新问题"
        assert len(msgs) == 4

    @pytest.mark.asyncio
    async def test_chat_completion_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "OK"}}]}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch.object(doubao_client, "_cfg", return_value={
                "api_key": "k", "api_base": "http://x", "model": "m"
            }),
            patch("app.services.doubao_client.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await doubao_client.chat_completion(
                system_prompt="s", user_message="hi"
            )
        assert result == "OK"
