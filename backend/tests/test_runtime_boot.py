# -*- coding: utf-8 -*-
"""运行时 boot_id / 维护 / force_logout"""

import os

from app.core.runtime import (
    get_boot_id,
    init_runtime,
    is_maintenance,
    ping_payload,
    runtime_flags,
    should_force_logout,
    should_force_relogin_on_boot,
)


def test_init_runtime_boot_id_changes():
    a = init_runtime()
    b = init_runtime()
    assert a != b
    assert get_boot_id() == b


def test_ping_payload_includes_boot_fields():
    init_runtime()
    data = ping_payload()
    assert data["boot_id"]
    assert "force_relogin_on_boot" in data
    assert "maintenance" in data
    assert "force_logout" in data
    assert should_force_relogin_on_boot() is True


def test_maintenance_and_force_logout_env(monkeypatch):
    init_runtime()
    monkeypatch.setenv("JNAO_MAINTENANCE", "1")
    monkeypatch.setenv("JNAO_MAINTENANCE_MSG", "升级中")
    monkeypatch.setenv("JNAO_FORCE_LOGOUT", "1")
    assert is_maintenance() is True
    assert should_force_logout() is True
    flags = runtime_flags()
    assert flags["maintenance"] is True
    assert flags["maintenance_message"] == "升级中"
    assert flags["force_logout"] is True
    assert ping_payload()["ok"] is False


def test_ping_api(client):
    res = client.get("/api/ping")
    assert res.status_code == 200
    body = res.json()
    assert body.get("boot_id")
    assert "maintenance" in body
    assert "force_logout" in body


def test_meta_version_api(client):
    res = client.get("/api/meta/version")
    assert res.status_code == 200
    body = res.json()
    assert "build_id" in body
    assert "boot_id" in body
    assert "maintenance" in body
