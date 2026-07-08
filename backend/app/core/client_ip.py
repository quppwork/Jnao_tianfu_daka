"""客户端 IP — 仅信任代理列表内的 X-Forwarded-For（B9）"""

from __future__ import annotations

import os

from fastapi import Request


def _trusted_proxies() -> set[str]:
    raw = os.getenv("TRUSTED_PROXY_IPS", "127.0.0.1,::1")
    return {x.strip() for x in raw.split(",") if x.strip()}


def client_ip_from_request(request: Request) -> str:
    remote = ""
    if request.client:
        remote = (request.client.host or "").strip()
    trusted = _trusted_proxies()
    if remote in trusted:
        forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return remote


def device_id_from_request(request: Request) -> str:
    return (request.headers.get("x-device-id") or request.headers.get("X-Device-Id") or "").strip()[:64]
