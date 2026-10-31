"""中央电脑 — 段位 / 四境 / 经验 / 排名纯函数测试。"""

from app.services.growth_tier_period import (
    assign_competition_ranks,
    clamp_tier,
    competition_ranks,
    compute_process_xp,
    compute_result_xp,
    duan_label,
    lcd_advice,
    lock_progress,
    tier_view,
    xp_bar,
)


def test_lv_equals_overall_tier_and_duan():
    v = tier_view(3)
    assert v["level"] == 3
    assert v["overall_tier"] == 3
    assert v["duan_label"] == "筑基期·三段"
    assert v["period_name"] == "筑基期"


def test_period_boundaries():
    assert tier_view(1)["period_key"] == "zhuji"
    assert tier_view(4)["period_key"] == "kaiqiao"
    assert tier_view(7)["period_key"] == "rongtong"
    assert tier_view(9)["period_key"] == "jianfeng"
    assert duan_label(9) == "尖峰期·九段"


def test_lock_progress_partial_then_full():
    locks = lock_progress(1)
    assert locks[0]["filled"] == 1 and locks[0]["total"] == 3
    assert abs(locks[0]["ratio"] - 1 / 3) < 1e-6
    assert locks[0]["open"] is False

    locks2 = lock_progress(2)
    assert locks2[0]["filled"] == 2
    assert abs(locks2[0]["ratio"] - 2 / 3) < 1e-6

    locks3 = lock_progress(3)
    assert locks3[0]["open"] is True
    assert locks3[0]["ratio"] == 1.0
    assert locks3[1]["filled"] == 0


def test_lock_progress_mid_kaiqiao():
    locks = lock_progress(5)
    assert locks[0]["open"] is True
    assert locks[1]["filled"] == 2
    assert locks[1]["open"] is False


def test_competition_ranks_skip_after_tie():
    assert competition_ranks([9, 8, 8, 7]) == [1, 2, 2, 4]
    rows = assign_competition_ranks(
        [
            {"name": "A", "level": 3},
            {"name": "B", "level": 3},
            {"name": "C", "level": 2},
        ]
    )
    assert rows[0]["rank"] == 1 and rows[1]["rank"] == 1
    assert rows[2]["rank"] == 3


def test_xp_bar_process_and_result():
    proc = compute_process_xp([60, 40])
    res = compute_result_xp(2)
    assert proc == 100
    assert res == 80
    bar = xp_bar(process_xp=proc, result_xp=res, overall_tier=3)
    assert bar["level"] == 3
    assert bar["total_xp"] == 180
    assert 0 <= bar["bar_pct"] <= 100


def test_lcd_advice_uses_streak_and_today():
    assert "蓄能" in lcd_advice(streak=0, today_checked=False, total_days=0)
    assert "已打卡" in lcd_advice(streak=2, today_checked=True, total_days=5)


def test_clamp_tier():
    assert clamp_tier(0) == 1
    assert clamp_tier(99) == 9
