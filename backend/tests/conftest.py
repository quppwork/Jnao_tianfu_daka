import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_jnao():
    """Mock JNAO submit + get_report to avoid real HTTP calls."""
    with (
        patch("app.api.talent.jnao_submit", new_callable=AsyncMock) as mock_submit,
        patch("app.api.talent.jnao_get_report", new_callable=AsyncMock) as mock_report,
    ):
        mock_submit.return_value = "test-record-123"
        mock_report.return_value = {
            "id": 123, "uid": 999888, "type": 0,
            "talent": "学者", "check_talent": "学者",
            "create_time": "2026-06-18",
            "results": {},
            "property": "[]", "AttributeJs": "{}", "StateIcon": "",
        }
        yield {"submit": mock_submit, "report": mock_report}


@pytest.fixture
def client(mock_jnao):
    """FastAPI TestClient with mocked JNAO."""
    from main import app
    return TestClient(app)


@pytest.fixture
def mock_ai_proxy():
    """Mock AI proxy for chat endpoint tests."""
    with patch("app.api.chat.ai_proxy", new_callable=AsyncMock) as mock:
        mock.chat = AsyncMock(return_value={
            "answer": "这是一条测试回复",
            "sources": [{"title": "来源1", "url": "http://example.com"}],
            "answer_mode": "rag",
        })
        mock.check_health = AsyncMock(return_value=True)
        yield mock
