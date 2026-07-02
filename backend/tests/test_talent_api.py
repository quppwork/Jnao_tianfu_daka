import pytest
"""Backend API tests — talent report endpoint"""

import pytest
from fastapi.testclient import TestClient


class TestReportEndpoint:
    """POST /api/talent/report"""

    def test_normal_submit_returns_report(self, client: TestClient, mock_jnao):
        """正常提交 35 位编码，应返回报告数据."""
        res = client.post("/api/talent/report", json={
            "answer": "11000111110001001001011111000101001",
            "uid": 999888,
            "type": 0,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["code"] == 1
        assert data["data"]["id"] == 123
        assert data["data"]["talent"] == "学者"
        mock_jnao["submit"].assert_called_once_with("11000111110001001001011111000101001", 999888, 0)

    def test_child_type_report(self, client: TestClient, mock_jnao):
        """孩子测试 type=1."""
        res = client.post("/api/talent/report", json={
            "answer": "00000000000000000000000000000000000",
            "uid": 111222,
            "type": 1,
        })
        assert res.status_code == 200
        assert res.json()["code"] == 1
        mock_jnao["submit"].assert_called_once_with("00000000000000000000000000000000000", 111222, 1)

    def test_answer_too_short_422(self, client: TestClient):
        """answer 不足 35 位应返回 422."""
        res = client.post("/api/talent/report", json={
            "answer": "10101",
            "uid": 123456,
            "type": 0,
        })
        assert res.status_code == 422

    def test_answer_too_long_422(self, client: TestClient):
        """answer 超过 35 位应返回 422."""
        res = client.post("/api/talent/report", json={
            "answer": "1" * 36,
            "uid": 123456,
            "type": 0,
        })
        assert res.status_code == 422

    def test_missing_answer_422(self, client: TestClient):
        """缺少 answer 字段应返回 422."""
        res = client.post("/api/talent/report", json={
            "uid": 123456,
            "type": 0,
        })
        assert res.status_code == 422

    def test_invalid_type_422(self, client: TestClient):
        """type 不是 0 或 1 应返回 422."""
        res = client.post("/api/talent/report", json={
            "answer": "11000111110001001001011111000101001",
            "uid": 123456,
            "type": 2,
        })
        assert res.status_code == 422

    def test_jnao_submit_error_returns_502(self, client: TestClient, mock_jnao):
        """JNAO 提交失败时返回 502."""
        mock_jnao["submit"].side_effect = RuntimeError("JNAO 超时")
        res = client.post("/api/talent/report", json={
            "answer": "11000111110001001001011111000101001",
            "uid": 999888,
            "type": 0,
        })
        assert res.status_code == 502

    def test_jnao_report_error_returns_502(self, client: TestClient, mock_jnao):
        """JNAO 报告获取失败时返回 502."""
        mock_jnao["report"].side_effect = RuntimeError("报告不存在")
        res = client.post("/api/talent/report", json={
            "answer": "11000111110001001001011111000101001",
            "uid": 999888,
            "type": 0,
        })
        assert res.status_code == 502
