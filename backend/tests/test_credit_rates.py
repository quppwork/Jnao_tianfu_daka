"""算力价目与额度拦截（不打真实模型）。"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.model_cost.rates import (
    RATE_VERSION,
    default_rate_card,
    estimate_usage_cost,
    is_deepseek_peak,
    milli_cent_to_yuan,
    yuan_per_1m_to_milli_per_1k,
)
from app.services.credit_service import credit_enforce_enabled, tokens_to_points

_TZ = ZoneInfo("Asia/Shanghai")


def test_yuan_per_1m_conversion():
    assert yuan_per_1m_to_milli_per_1k(0.5) == 50
    assert yuan_per_1m_to_milli_per_1k(1.0) == 100
    assert yuan_per_1m_to_milli_per_1k(4.0) == 400


def test_flash_idle_official_price():
    """deepseek-flash 空闲：输入未命中 ¥1/1M，输出 ¥4/1M。"""
    idle = datetime(2026, 11, 1, 20, 0, tzinfo=_TZ)  # Sun evening
    assert is_deepseek_peak(idle) is False
    milli, ver = estimate_usage_cost(
        provider="deepseek",
        model="deepseek-flash",
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
        at=idle,
    )
    assert ver == RATE_VERSION
    # 1M * 1 + 1M * 4 = ¥5 → 500_000 milli-cent
    assert milli == 500_000
    assert abs(milli_cent_to_yuan(milli) - 5.0) < 1e-9


def test_flash_peak_and_cache_hit():
    peak = datetime(2026, 11, 2, 10, 0, tzinfo=_TZ)  # Mon 10:00
    assert is_deepseek_peak(peak) is True
    # 500k hit @ 0.04 + 500k miss @ 2 + 0 out = ¥1.02 / 百万档 → 实际半百万各
    milli, _ = estimate_usage_cost(
        provider="deepseek",
        model="deepseek-flash",
        prompt_tokens=1_000_000,
        completion_tokens=0,
        prompt_cache_hit_tokens=500_000,
        at=peak,
    )
    # hit 0.5M * 0.04 + miss 0.5M * 2 = 0.02 + 1 = ¥1.02 → 102_000 milli-cent
    assert milli == 102_000


def test_pro_resolves_separate_band():
    idle = datetime(2026, 11, 1, 20, 0, tzinfo=_TZ)
    milli, _ = estimate_usage_cost(
        provider="deepseek",
        model="deepseek-v4-pro",
        prompt_tokens=1_000_000,
        completion_tokens=0,
        at=idle,
    )
    # pro idle miss ¥4.5 / 1M
    assert milli == 450_000


def test_legacy_flash_alias_maps_to_v41():
    card = default_rate_card()
    a = card.resolve("deepseek", "deepseek-v4-flash")
    b = card.resolve("deepseek", "deepseek-flash")
    assert a.model == b.model == "deepseek-flash"


def test_tokens_to_points():
    assert tokens_to_points(0) == 0
    assert tokens_to_points(999) == 0
    assert tokens_to_points(1000) == 1
    assert tokens_to_points(2500) == 2


def test_credit_enforce_default_off(monkeypatch):
    monkeypatch.delenv("CREDIT_ENFORCE", raising=False)
    assert credit_enforce_enabled() is False
    monkeypatch.setenv("CREDIT_ENFORCE", "1")
    assert credit_enforce_enabled() is True
