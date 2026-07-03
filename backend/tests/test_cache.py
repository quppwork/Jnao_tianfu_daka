"""Redis 缓存层 — 无 REDIS_URL 时透明降级"""

from datetime import date

from app.core import cache as cache_mod


def test_cache_noop_without_redis(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    cache_mod._redis_checked = False
    cache_mod._redis = None

    assert cache_mod.cache_get_json("jnao:test:1") is None
    cache_mod.cache_set_json("jnao:test:1", {"ok": True}, 60)
    cache_mod.cache_delete("jnao:test:1")
    cache_mod.invalidate_user_training(1, plan_date=date.today())


def test_key_helpers():
    assert cache_mod.key_profile(7) == "jnao:profile:7"
    assert cache_mod.key_train_today(3, date(2026, 7, 3)) == "jnao:train:today:3:2026-07-03"
