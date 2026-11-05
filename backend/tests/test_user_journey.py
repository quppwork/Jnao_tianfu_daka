"""v3.0 用户旅程模拟测试 — 新用户→10天训练→升阶→捆绑

覆盖场景：
  新用户首日 / 连续短时触发策略切换 / 时长全档位 / Tier 升阶 / 捆绑选择
"""

from datetime import date, timedelta

import pytest
from app.services.training_formula_engine import (
    HistoryEntry,
    expand_formula,
)


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

BASE = date(2026, 7, 1)

# 各阶默认个体 Tier（所有技能同级）
_TIER1_SKILLS = {"超脑阅读": 1, "影像追忆": 1, "扫描速记": 1,
                 "极速运算": 1, "极速学习": 1}
_TIER3_SKILLS = {"超脑阅读": 3, "影像追忆": 3, "扫描速记": 3,
                 "极速运算": 3, "极速学习": 3}


def _h(days: list[int], minutes: int,
       skills: tuple[str, ...] = ("超脑阅读",)) -> tuple[HistoryEntry, ...]:
    """快捷构造历史：指定偏移天数列表 + 统一时长"""
    return tuple(
        HistoryEntry(plan_date=BASE + timedelta(days=d),
                     planned_minutes=minutes, skills=skills)
        for d in days
    )


def _call(minutes: int, tier: int = 1, grade: str = "primary_low",
          skill_tiers: dict | None = None, history: tuple = ()) -> dict:
    return expand_formula(
        minutes, overall_tier=tier, grade_band=grade,
        skill_tiers=skill_tiers or _TIER1_SKILLS,
        history=history,
    )


# ═══════════════════════════════════════════════════════════════
# 旅程 1：新用户 10 天训练
# ═══════════════════════════════════════════════════════════════

class TestNewUserJourney:
    """新用户从 Day1 到 Day10，覆盖全部时长档位 + 策略切换"""

    # ── Day 1：新用户，选 2h（120min）──

    def test_day1_new_user_120min(self):
        """首日无历史，120min→3槽，权重贪心"""
        r = _call(120)
        assert r["strategy"] == "weight_based"
        assert len(r["slots"]) == 3
        # Tier 1 权重 A=0.40 B=0.35 C=0.12: [A, B, A]
        assert r["slots"] == ["超脑阅读", "影像追忆", "超脑阅读"]

    # ── Day 2：中等时长 40min ──

    def test_day2_40min(self):
        # 昨日真实技能进 history，A/B 同受软惩罚 → 相对序与无惩罚一致
        r = _call(40, history=_h([1], 120, skills=("超脑阅读", "影像追忆", "超脑阅读")))
        assert r["strategy"] == "weight_based"
        assert len(r["slots"]) == 2
        assert r["slots"] == ["超脑阅读", "影像追忆"]

    # ── Day 3-8：短时积累仍走主干（历史软惩罚，无旁路）──

    def test_day3_short_20min_accumulating(self):
        """Day3: 连续2天短时 → weight_based"""
        r = _call(20, history=_h([1, 2], 20))
        assert r["strategy"] == "weight_based"
        assert len(r["slots"]) == 1

    def test_day7_6days_short_still_normal(self):
        """Day7: 前6天短时 → weight_based"""
        r = _call(20, history=_h([1, 2, 3, 4, 5, 6], 20))
        assert r["strategy"] == "weight_based"

    def test_day8_7days_short_stays_on_trunk(self):
        """Day8: 前7天短时 → 仍主干；近史超脑被软惩罚 → 倾向影像"""
        r = _call(20, history=_h([1, 2, 3, 4, 5, 6, 7], 20))
        assert r["strategy"] == "weight_based"
        assert len(r["slots"]) == 1
        assert r["slots"][0] == "影像追忆"

    # ── Day 9：长时长仍主干 ──

    def test_day9_back_to_180min(self):
        """Day9: 选长时长 → 权重策略"""
        history = _h([1, 2, 3, 4, 5, 6, 7, 8], 20)
        r = _call(180, history=history)
        assert r["strategy"] == "weight_based"

    # ── Day 10：60min 边界档位 ──

    def test_day10_60min(self):
        r = _call(60, history=_h([9], 180, skills=("超脑阅读", "影像追忆", "超脑阅读")))
        assert r["strategy"] == "weight_based"
        assert len(r["slots"]) == 3
        assert r["slots"] == ["超脑阅读", "影像追忆", "超脑阅读"]


# ═══════════════════════════════════════════════════════════════
# 旅程 2：连续短时仍走主干（历史软惩罚，无旁路）
# ═══════════════════════════════════════════════════════════════

class TestShortStreakOnTrunk:
    """连续短时不再切换策略；多样性由 greedy 近史软惩罚承担"""

    def test_day14_still_weight_based(self):
        r = _call(20, history=_h(list(range(1, 15)), 20))
        assert r["strategy"] == "weight_based"
        assert r["minutes"] == 20
        assert len(r["slots"]) == 1

    def test_day15_after_longer_day(self):
        h = _h(list(range(1, 14)), 20) + _h([14], 40)
        r = _call(20, history=h)
        assert r["strategy"] == "weight_based"

    def test_soft_penalty_after_long_short_streak(self):
        r = _call(20, history=_h(list(range(1, 15)), 20))
        assert r["slots"][0] == "影像追忆"


# ═══════════════════════════════════════════════════════════════
# 旅程 3：升阶到 Tier 3 → 捆绑排课
# ═══════════════════════════════════════════════════════════════

class TestTier3Progression:
    """用户从 Tier 1 升到 Tier 3，捆绑规则生效"""

    # ── 场景 A：各技能个体 Tier 均衡 ──

    def test_tier3_all_balanced(self):
        """所有技能 Tier=3 → 捆绑选择：全部 min_tier=3，字母序破平 → B3"""
        r = _call(120, tier=3, skill_tiers=_TIER3_SKILLS)
        assert r["strategy"] == "weight_with_bundle"
        assert r["bundle_id"] is not None
        # B3: 影像追忆(B) 字母序最小 → 优先
        assert r["bundle_id"] == "B3"
        assert "极速运算" in r["slots"]

    # ── 场景 B：极速运算刚刚引入（个体 Tier 低）──

    def test_tier3_D_just_introduced(self):
        """极速运算(D) 个体 Tier=1，其他技能已到 Tier 3"""
        st = {"超脑阅读": 3, "影像追忆": 3, "扫描速记": 3,
              "极速运算": 1, "极速学习": 2}
        r = _call(120, tier=3, skill_tiers=st)
        assert r["strategy"] == "weight_with_bundle"
        # D tier=1 在所有捆绑中 → 全部 min_tier=1
        # 破平看搭档：B3 影像追忆(tier=3) < B2 扫描速记(tier=3) → B3
        # 实际上字母序：B(B3) < C(B2) < D(B1,B4) → B3
        assert r["bundle_id"] == "B3"

    # ── 场景 C：扫描速记落后 → B2 优先 ──

    def test_tier3_C_behind_B2_priority(self):
        """扫描速记(C) Tier=1，其他 Tier≥2 → B2 优先"""
        st = {"超脑阅读": 3, "影像追忆": 3, "扫描速记": 1,
              "极速运算": 2, "极速学习": 3}
        r = _call(120, tier=3, skill_tiers=st)
        assert r["strategy"] == "weight_with_bundle"
        # B2: C(tier=1)+D(tier=2) → min=1, code=C
        # B3: B(tier=3)+D(tier=2) → min=2
        # B4: D(tier=2)+E(tier=3) → min=2
        # B2 的 min_tier=1 唯一最低 → B2 胜出
        assert r["bundle_id"] == "B2"

    # ── 场景 D：极速学习落后 → B4 优先 ──

    def test_tier3_E_behind_B4_priority(self):
        """极速学习(E) Tier=1，其他 Tier≥2 → B4 优先"""
        st = {"超脑阅读": 3, "影像追忆": 3, "扫描速记": 2,
              "极速运算": 2, "极速学习": 1}
        r = _call(120, tier=3, skill_tiers=st)
        assert r["strategy"] == "weight_with_bundle"
        # B4: D(tier=2)+E(tier=1) → min=1
        # B1: 多元感知(无)+D(tier=2) → min=2
        # B2: C(tier=2)+D(tier=2) → min=2
        # B3: B(tier=3)+D(tier=2) → min=2
        # B4 min=1 唯一最低 → B4
        assert r["bundle_id"] == "B4"

    # ── 场景 E：Tier 3 长方案，捆绑后权重补位 ──

    def test_tier3_long_plan_with_fill(self):
        """180min=4槽，B3捆绑2槽 + 权重补位2槽"""
        st = {"超脑阅读": 3, "影像追忆": 3, "扫描速记": 2,
              "极速运算": 2, "极速学习": 2}
        r = _call(180, tier=3, skill_tiers=st)
        assert r["strategy"] == "weight_with_bundle"
        # B3 (2槽) + 权重补位 (2槽) → 共4技能
        assert len(r["slots"]) >= 3  # 至少3项


# ═══════════════════════════════════════════════════════════════
# 旅程 4：全时长档位覆盖
# ═══════════════════════════════════════════════════════════════

class TestAllDurationTiers:
    """20 / 40 / 60-120 / 121-180 / 181-240 / 241-300 / 480+ 全部档位"""

    # (minutes, expected_必修_slots)
    DURATIONS = [
        (20,  1),
        (40,  2),
        (60,  3),
        (90,  3),
        (120, 3),
        (150, 4),   # 4必修 + 1高效作业 = 5 total
        (200, 4),   # 4必修 + 1高效作业 = 5 total
        (250, 5),   # 5必修 + 1高效作业 = 6 total
        (300, 5),   # 5必修 + 1高效作业 = 6 total
        (480, 6),   # 6必修 + 精力恢复 ≥ 7 total
    ]

    @pytest.mark.parametrize("minutes,必修_slots", DURATIONS)
    def test_duration_homework_appended(self, minutes, 必修_slots):
        r = _call(minutes)
        assert r["strategy"] == "weight_based"
        total = len(r["slots"])
        # ≥121min → 额外高效作业槽
        if minutes >= 121:
            assert total >= 必修_slots + 1
            assert "高效作业" in r["slots"]
        # ≥480min → 额外精力恢复
        if minutes >= 480:
            assert "精力恢复" in r["slots"]
            assert r["slots"][-1] == "精力恢复"

    def test_tier1_150min_has_homework(self):
        r = _call(150, tier=1)
        assert "高效作业" in r["slots"]

    def test_tier3_150min_has_speed_learn_not_homework(self):
        """Tier≥3: 高效作业→极速学习"""
        st = {"超脑阅读": 3, "影像追忆": 3, "扫描速记": 3,
              "极速运算": 3, "极速学习": 3}
        r = _call(150, tier=3, skill_tiers=st)
        assert "高效作业" not in r["slots"]
        assert "极速学习" in r["slots"]

    def test_tier3_200min_has_2E(self):
        """181-240min Tier≥3: 2个极速学习"""
        st = {"超脑阅读": 3, "影像追忆": 3, "扫描速记": 3,
              "极速运算": 3, "极速学习": 3}
        r = _call(200, tier=3, skill_tiers=st)
        e_count = r["slots"].count("极速学习")
        assert e_count >= 2, f"Expected ≥2E, got {e_count}"

    def test_tier3_250min_has_3E(self):
        """241-300min Tier≥3: 3个极速学习"""
        st = {"超脑阅读": 3, "影像追忆": 3, "扫描速记": 3,
              "极速运算": 3, "极速学习": 3}
        r = _call(250, tier=3, skill_tiers=st)
        e_count = r["slots"].count("极速学习")
        assert e_count >= 3, (
            f"Expected ≥3E, got {e_count}"
        )

    def test_480min_has_energy_recovery(self):
        r = _call(480)
        assert "精力恢复" in r["slots"]
        # 精力恢复在末尾
        assert r["slots"][-1] == "精力恢复"


# ═══════════════════════════════════════════════════════════════
# 旅程 5：Tier 5/6 高阶技能引入
# ═══════════════════════════════════════════════════════════════

class TestHighTierSkills:
    """Tier 5 引入 F/G，Tier 6 引入 H/I"""

    def test_tier5_FG_in_front(self):
        """Tier 5: F(0.20) G(0.20) 权重最高 → 短时方案应出现"""
        st = {"超脑阅读": 5, "影像追忆": 5, "扫描速记": 5,
              "极速运算": 5, "极速学习": 5,
              "文科奥秘": 5, "理科奥秘": 5}
        r = _call(40, tier=5, skill_tiers=st)
        skills = r["slots"]
        # F=0.20 G=0.20 B=0.18 → 前两个是 F/G
        assert skills[0] in ("文科奥秘", "理科奥秘")
        assert skills[1] in ("文科奥秘", "理科奥秘")
        assert skills[0] != skills[1]  # F 衰减后 G 顶上

    def test_tier6_HI_art_first(self):
        """Tier 6: B=0.22 H=0.22 I=0.22 权重相等，按 dict 序 B 先"""
        st = {"影像追忆": 6, "扫描速记": 6, "极速运算": 6,
              "天赋绘画": 6, "音乐灵感": 6}
        r = _call(120, tier=6, skill_tiers=st)
        skills = r["slots"]
        # dict 序: B(0.22)→H(0.22)→I(0.22)→B(0.154)...
        # 120min=3槽: [B, H, I]
        assert len(skills) == 3
        # B 权重与 H/I 相同但 dict 序靠前 → B 第一
        # H/I 应在 slots 中
        assert "天赋绘画" in skills
        assert "音乐灵感" in skills
        assert "影像追忆" in skills

    def test_tier6_no_bundle(self):
        """Tier 6 无捆绑 → weight_based 策略"""
        st = {"影像追忆": 6, "扫描速记": 6, "极速运算": 6,
              "天赋绘画": 6, "音乐灵感": 6}
        r = _call(120, tier=6, skill_tiers=st)
        assert r["strategy"] == "weight_based"
        assert r["bundle_id"] is None


# ═══════════════════════════════════════════════════════════════
# 旅程 6：学段差异
# ═══════════════════════════════════════════════════════════════

class TestGradeDifferences:
    """不同学段的标注行为"""

    def test_primary_low_no_mark(self):
        r = _call(120, grade="primary_low")
        assert r["c_note"] is None

    def test_primary_high_no_mark(self):
        r = _call(120, grade="primary_high")
        assert r["c_note"] is None

    def test_junior_c_marked_when_present(self):
        r = _call(120, grade="junior")
        # 扫描速记在 slots 中 → 标记
        if "扫描速记" in r["slots"]:
            assert r["c_note"] == "不推荐"

    def test_senior_c_marked_when_present(self):
        r = _call(120, grade="senior")
        if "扫描速记" in r["slots"]:
            assert r["c_note"] == "不推荐"

    def test_junior_tier3_bundle_B2_marked(self):
        """初中 Tier 3 选 B2 → 标记不推荐"""
        st = {"超脑阅读": 3, "影像追忆": 3, "扫描速记": 1,
              "极速运算": 2, "极速学习": 3}
        r = _call(120, tier=3, grade="junior", skill_tiers=st)
        # B2 优先（扫描速记 tier=1）
        if r["bundle_id"] == "B2":
            assert r["bundle_note"] == "不推荐"


# ═══════════════════════════════════════════════════════════════
# 旅程 7：衰减与阈值
# ═══════════════════════════════════════════════════════════════

class TestDecayAndThreshold:
    """权重衰减 + <0.01 排除"""

    def test_long_plan_excludes_low_weight_skills(self):
        """长方案中，低权重技能多次衰减后应被排除"""
        r = _call(300, tier=1)
        # A/B 权重高，C/D/E 权重低 → D/E 可能被排除
        # 至少 A/B 会出现
        unique = set(r["slots"])
        assert "超脑阅读" in unique or "影像追忆" in unique

    def test_deterministic_across_multiple_calls(self):
        """多次调用结果一致"""
        results = [_call(120)["slots"] for _ in range(5)]
        for r in results[1:]:
            assert r == results[0]

    def test_tier1_short_no_DE(self):
        """Tier 1 短时方案不应出现极速运算/极速学习（权重过低）"""
        r = _call(20, tier=1)
        assert r["slots"][0] not in ("极速运算", "极速学习")

    def test_tier3_D_must_appear(self):
        """Tier 3 捆绑策略 → 极速运算必然出现"""
        st = {"超脑阅读": 3, "影像追忆": 3, "扫描速记": 3,
              "极速运算": 2, "极速学习": 2}
        r = _call(120, tier=3, skill_tiers=st)
        assert "极速运算" in r["slots"]


# ═══════════════════════════════════════════════════════════════
# 旅程 8：边界与异常
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    """边界条件"""

    def test_nonstandard_minutes_25(self):
        """25min 无精确档 → floor 到 20min = 1 槽"""
        r = _call(25)
        assert len(r["slots"]) == 1

    def test_minimal_minutes_20(self):
        """最小合法时长 20min"""
        r = _call(20)
        assert len(r["slots"]) == 1
        assert r["minutes"] == 20

    def test_large_minutes_600(self):
        """600min → 最高档 6+ 槽"""
        r = _call(600)
        assert len(r["slots"]) >= 6
        if 600 >= 480:
            assert "精力恢复" in r["slots"]

    def test_empty_skill_tiers(self):
        """skill_tiers={} → 捆绑默认全部 Tier=99，字母序破平"""
        r = _call(60, tier=3, skill_tiers={})
        assert r["strategy"] == "weight_with_bundle"
        # 全部 min_tier=99 → 字母序 B3(B) 胜出
        assert r["bundle_id"] == "B3"

    def test_missing_skill_in_tiers(self):
        """skill_tiers 缺少某些技能 → 缺失的按 99 处理"""
        st = {"影像追忆": 3}  # 只给了影像追忆
        r = _call(60, tier=3, skill_tiers=st)
        assert r["strategy"] == "weight_with_bundle"
        # D 不在 skill_tiers 中 → tier=99
        # B3: B(tier=3)+D(tier=99) → min=3
        # 其他捆绑 D(tier=99) → min 更高
        # B3 min=3 最低 → B3
        assert r["bundle_id"] == "B3"

    def test_tier2_no_bundle(self):
        """Tier 2 无捆绑 → weight_based"""
        r = _call(120, tier=2)
        assert r["strategy"] == "weight_based"
        assert r["bundle_id"] is None

    def test_tier4_no_bundle(self):
        """Tier 4 无捆绑 → weight_based"""
        st = {"超脑阅读": 4, "影像追忆": 4, "扫描速记": 4,
              "极速运算": 4, "极速学习": 4}
        r = _call(120, tier=4, skill_tiers=st)
        assert r["strategy"] == "weight_based"
        assert r["bundle_id"] is None


# ═══════════════════════════════════════════════════════════════
# 旅程 9：加权对比 — 不同 skill_tiers 下的捆绑分布
# ═══════════════════════════════════════════════════════════════

class TestBundleSelectionMatrix:
    """验证捆绑选择在多种 skill_tiers 组合下的正确性"""

    SCENARIOS = [
        # (skill_tiers, expected_bundle, description)
        ({"影像追忆": 1, "扫描速记": 3, "极速运算": 1, "极速学习": 3},
         "B3", "影像追忆 tier=1 最低 → B3"),
        ({"影像追忆": 3, "扫描速记": 1, "极速运算": 2, "极速学习": 3},
         "B2", "扫描速记 tier=1 最低 → B2"),
        ({"影像追忆": 3, "扫描速记": 3, "极速运算": 1, "极速学习": 1},
         "B3", "全部 min_tier=1, 字母序 B3(B) 最优"),
        ({"影像追忆": 2, "扫描速记": 2, "极速运算": 2, "极速学习": 1},
         "B4", "极速学习 tier=1 最低 → B4"),
        ({"影像追忆": 3, "扫描速记": 3, "极速运算": 3, "极速学习": 3},
         "B3", "全部 tier=3, 字母序破平 → B3"),
    ]

    @pytest.mark.parametrize("skill_tiers,expected,desc", SCENARIOS)
    def test_bundle_selection(self, skill_tiers, expected, desc):
        st = {"超脑阅读": 3, **skill_tiers}
        r = _call(60, tier=3, skill_tiers=st)
        assert r["bundle_id"] == expected, (
            f"{desc}\n  skill_tiers={skill_tiers}\n  got={r['bundle_id']}"
        )
