"""客户端 IP — 仅信任代理列表内的 X-Forwarded-For（B9）"""

from __future__ import annotations

import os

from fastapi import Request


def _trusted_proxies() -> set[str]:
    raw = os.getenv("TRUSTED_PROXY_IPS", "127.0.0.1,::1")
    return {x.strip() for x in raw.split(",") if x.strip()}


def _is_private_or_loopback(ip: str) -> bool:
    """Docker / 内网反代常见：直连 IP 为私有地址时仍应信任 X-Forwarded-For。"""
    if not ip or ip == "localhost":
        return True
    if ip in ("127.0.0.1", "::1"):
        return True
    if ip.startswith("::ffff:"):
        ip = ip[7:]
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        a, b, _, _ = (int(x) for x in parts)
    except ValueError:
        return False
    if a == 10:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    if a == 192 and b == 168:
        return True
    return False


def client_ip_from_request(request: Request) -> str:
    remote = ""
    if request.client:
        remote = (request.client.host or "").strip()
    forwarded = (request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For") or "").strip()
    trusted = _trusted_proxies()
    if forwarded and (remote in trusted or _is_private_or_loopback(remote)):
        return forwarded.split(",")[0].strip()
    return remote


def device_id_from_request(request: Request) -> str:
    return (request.headers.get("x-device-id") or request.headers.get("X-Device-Id") or "").strip()[:64]
