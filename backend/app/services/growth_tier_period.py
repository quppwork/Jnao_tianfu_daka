"""中央电脑 — 九段 / 四境 / 经验条 / 并列排名（纯函数，无 DB）。

口径（产品拍板）：
- 等级 Lv.N = overall_tier（1-9）=「筑基期·N段」同一字段
- 累计训练时长计入经验条（过程）；段位晋级主因仍是打卡达标（结果）
- 天梯并列：同分同名次，下一档跳号（11、11、13）
"""

from __future__ import annotations

from typing import Any

_CN = ("零", "一", "二", "三", "四", "五", "六", "七", "八", "九")

# 四境：段位区间与锁进度格数
PERIODS: tuple[dict[str, Any], ...] = (
    {
        "key": "zhuji",
        "name": "筑基期",
        "tiers": (1, 2, 3),
        "lock_index": 1,
    },
    {
        "key": "kaiqiao",
        "name": "开窍期",
        "tiers": (4, 5, 6),
        "lock_index": 2,
    },
    {
        "key": "rongtong",
        "name": "融通期",
        "tiers": (7, 8),
        "lock_index": 3,
    },
    {
        "key": "jianfeng",
        "name": "尖峰期",
        "tiers": (9,),
        "lock_index": 4,
    },
)

# 经验条：过程（分钟）+ 结果（达标次数）权重；条满只表示本段过程积累，不直接升段
XP_PER_PLANNED_MIN = 1.0
XP_PER_PASS = 40.0
XP_BAR_PER_TIER = 300.0  # 约 5 小时规划量填满一条


def clamp_tier(overall_tier: int | None) -> int:
    try:
        t = int(overall_tier or 1)
    except (TypeError, ValueError):
        t = 1
    return max(1, min(9, t))


def period_for_tier(overall_tier: int) -> dict[str, Any]:
    t = clamp_tier(overall_tier)
    for p in PERIODS:
        if t in p["tiers"]:
            return p
    return PERIODS[0]


def duan_label(overall_tier: int) -> str:
    """如：筑基期·三段"""
    t = clamp_tier(overall_tier)
    p = period_for_tier(t)
    return f"{p['name']}·{_CN[t]}段"


def tier_view(overall_tier: int) -> dict[str, Any]:
    """Lv / 段位 / 境期统一视图。"""
    t = clamp_tier(overall_tier)
    p = period_for_tier(t)
    return {
        "level": t,  # Lv.N
        "overall_tier": t,
        "period_key": p["key"],
        "period_name": p["name"],
        "duan_label": duan_label(t),
        "duan_short": f"{_CN[t]}段",
    }


def lock_progress(overall_tier: int) -> list[dict[str, Any]]:
    """四境之锁动态进度：1 段亮 1/3，2 段 2/3，3 段满锁，以此类推。"""
    t = clamp_tier(overall_tier)
    out: list[dict[str, Any]] = []
    for p in PERIODS:
        tiers = p["tiers"]
        total = len(tiers)
        lo, hi = tiers[0], tiers[-1]
        if t < lo:
            filled = 0
            open_ = False
        elif t >= hi:
            filled = total
            open_ = True
        else:
            filled = t - lo + 1
            open_ = False
        ratio = (filled / total) if total else 0.0
        out.append(
            {
                "key": p["key"],
                "name": p["name"],
                "lock_index": p["lock_index"],
                "tiers": list(tiers),
                "filled": filled,
                "total": total,
                "ratio": round(ratio, 6),
                "open": open_,
                "segs": [f"{_CN[x]}段" for x in tiers],
            }
        )
    return out


def xp_bar(*, process_xp: float, result_xp: float, overall_tier: int) -> dict[str, Any]:
    """经验条：过程+结果累计；条内百分比相对本段软上限，不替代升段。"""
    t = clamp_tier(overall_tier)
    total = max(0.0, float(process_xp) + float(result_xp))
    # 用段位偏移让高等级条有独立视觉区间（仍不升段）
    cap = XP_BAR_PER_TIER
    into = total % cap if cap else 0.0
    pct = min(100.0, round(into / cap * 100, 1)) if cap else 0.0
    return {
        "process_xp": round(process_xp, 1),
        "result_xp": round(result_xp, 1),
        "total_xp": round(total, 1),
        "bar_pct": pct,
        "bar_cap": cap,
        "level": t,
        "note": "经验条来自训练过程与打卡达标；升段仍以连续达标为准",
    }


def compute_process_xp(planned_minutes_done_days: list[int]) -> float:
    """已完成训练日的规划分钟 × 权重。"""
    return sum(max(0, int(m or 0)) for m in planned_minutes_done_days) * XP_PER_PLANNED_MIN


def compute_result_xp(pass_count: int) -> float:
    return max(0, int(pass_count or 0)) * XP_PER_PASS


def competition_ranks(sorted_scores_desc: list[float | int]) -> list[int]:
    """并列竞争名次：分数相同同名次，下一档跳号。

    例：[9,8,8,7] → [1,2,2,4]
    """
    ranks: list[int] = []
    for i, score in enumerate(sorted_scores_desc):
        if i == 0:
            ranks.append(1)
            continue
        if score == sorted_scores_desc[i - 1]:
            ranks.append(ranks[i - 1])
        else:
            ranks.append(i + 1)
    return ranks


def assign_competition_ranks(rows: list[dict[str, Any]], *, score_key: str = "level") -> list[dict[str, Any]]:
    """按 score_key 降序排序并写入 rank；同分同名次。"""
    ordered = sorted(rows, key=lambda r: (-int(r.get(score_key) or 0), str(r.get("name") or "")))
    scores = [int(r.get(score_key) or 0) for r in ordered]
    ranks = competition_ranks(scores)
    out: list[dict[str, Any]] = []
    for row, rank in zip(ordered, ranks):
        item = dict(row)
        item["rank"] = rank
        out.append(item)
    return out


def lcd_advice(*, streak: int, today_checked: bool, total_days: int) -> str:
    if today_checked:
        if streak >= 5:
            return "状态正好，明天可加 10 分钟巩固当前段位短板。"
        return "今日已打卡，保持节奏，连续达标才能升段。"
    if streak >= 5:
        return "连续势头不错，今天完成打卡就能保住连胜。"
    if total_days:
        return "上次打卡表现不错，今天先完成规划训练再打卡。"
    return "先完成今日第一关，中央电脑为你蓄能。"
