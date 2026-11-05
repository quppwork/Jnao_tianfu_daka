"""客户端 IP 解析（Docker 反代）"""

from unittest.mock import Mock

from app.core.client_ip import client_ip_from_request


def _req(remote: str, xff: str = "") -> Mock:
    r = Mock()
    r.client = Mock(host=remote)
    r.headers = {"x-forwarded-for": xff} if xff else {}
    return r


def test_trust_xff_from_docker_private_ip():
    req = _req("172.18.0.3", "223.5.5.5, 172.18.0.1")
    assert client_ip_from_request(req) == "223.5.5.5"


def test_no_xff_keeps_remote():
    req = _req("203.0.113.10", "")
    assert client_ip_from_request(req) == "203.0.113.10"
