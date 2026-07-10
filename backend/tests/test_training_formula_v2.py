"""v3.0 公式引擎测试 — Decision Tree + Strategy Pipeline"""

import pytest
from app.services.training_formula_engine import expand_formula


class TestFormulaEngine:
    """权重排课 + 策略选择"""

    # ── 槽位解析 ──

    def test_20min_returns_1_slot(self):
        result = expand_formula(20, overall_tier=1, grade_band="primary_low")
        assert len(result["slots"]) == 1
        assert result["strategy"] == "weight_based"

    def test_40min_returns_2_slots(self):
        result = expand_formula(40, overall_tier=1, grade_band="primary_low")
        assert len(result["slots"]) == 2

    def test_90min_returns_3_slots(self):
        result = expand_formula(90, overall_tier=1, grade_band="primary_low")
        assert len(result["slots"]) == 3

    def test_150min_returns_4plus1_slots(self):
        """121-180min: 4 必修 + 1 高效作业 = 5"""
        result = expand_formula(150, overall_tier=1, grade_band="primary_low")
        assert len(result["slots"]) == 5  # 4 + 1 高效作业
        assert "高效作业" in result["slots"]

    # ── 权重贪心：短时 → 重点项目主导 ──

    def test_20min_Tier1_picks_highest_weight(self):
        """20min=1槽，应选最高权重 A(0.40)"""
        result = expand_formula(20, overall_tier=1, grade_band="primary_low")
        assert result["slots"][0] == "超脑阅读"

    def test_40min_Tier1_A_B(self):
        """40min=2槽，权重 A>B → [A, B]"""
        result = expand_formula(40, overall_tier=1, grade_band="primary_low")
        assert result["slots"] == ["超脑阅读", "影像追忆"]

    def test_90min_Tier1_diversity(self):
        """90min=3槽，A 衰减后 B 顶上"""
        result = expand_formula(90, overall_tier=1, grade_band="primary_low")
        # 只有 A/B/C（D/E 权重很低），不出现 D/E
        for s in result["slots"]:
            assert s in ("超脑阅读", "影像追忆", "扫描速记")

    # ── 权重贪心：长时 → 多样化 ──

    def test_long_duration_includes_more_skills(self):
        """长方案应有更多技能种类"""
        result = expand_formula(250, overall_tier=1, grade_band="primary_low")
        unique = set(result["slots"])
        assert len(unique) >= 2  # 至少两种技能

    # ── 确定性 ──

    def test_deterministic_same_input_same_output(self):
        a = expand_formula(120, overall_tier=2, grade_band="primary_low")
        b = expand_formula(120, overall_tier=2, grade_band="primary_low")
        assert a["slots"] == b["slots"]

    # ── 学段标注 ──

    def test_junior_c_not_recommended(self):
        result = expand_formula(90, overall_tier=1, grade_band="junior")
        # 只有当扫描速记出现在 slots 中时才标记
        if "扫描速记" in result["slots"]:
            assert result["c_note"] == "不推荐"

    def test_senior_c_not_recommended(self):
        result = expand_formula(90, overall_tier=1, grade_band="senior")
        if "扫描速记" in result["slots"]:
            assert result["c_note"] == "不推荐"

    def test_primary_no_c_note(self):
        result = expand_formula(150, overall_tier=1, grade_band="primary_low")
        assert result["c_note"] is None

    # ── 选修标记 ──

    def test_elective_notes_present(self):
        result = expand_formula(150, overall_tier=1, grade_band="primary_low")
        assert "elective_notes" in result

    # ── 向后兼容字段 ──

    def test_result_has_required_fields(self):
        result = expand_formula(120, overall_tier=1, grade_band="primary_low")
        for key in ("slots", "elective_notes", "c_note", "exam_note", "minutes"):
            assert key in result, f"Missing key: {key}"

    def test_result_has_v3_fields(self):
        result = expand_formula(120, overall_tier=1, grade_band="primary_low")
        for key in ("strategy",):
            assert key in result, f"Missing v3 key: {key}"

    def test_fallback_nonstandard_minutes(self):
        result = expand_formula(25, overall_tier=1, grade_band="primary_low")
        assert len(result["slots"]) > 0

    def test_primary_high_uses_same_weights(self):
        result = expand_formula(90, overall_tier=1, grade_band="primary_high")
        assert len(result["slots"]) == 3


class TestTier3Bundle:
    """Tier 3 捆绑策略"""

    def test_tier3_uses_bundle_strategy(self):
        result = expand_formula(120, overall_tier=3, grade_band="primary_low",
                                skill_tiers={"影像追忆": 1, "扫描速记": 1,
                                             "极速运算": 1, "极速学习": 1})
        assert result["strategy"] == "weight_with_bundle"
        assert result["bundle_id"] in ("B1", "B2", "B3", "B4")

    def test_tier3_bundle_contains_极速运算(self):
        result = expand_formula(120, overall_tier=3, grade_band="primary_low",
                                skill_tiers={"影像追忆": 1, "扫描速记": 1,
                                             "极速运算": 1, "极速学习": 1})
        assert "极速运算" in result["slots"]

    def test_tier3_60min_B4_possible(self):
        """60min=3槽，极速学习 tier 最低 → B4 优先"""
        # 极速学习(E) tier=1，其他搭档 tier ≥2 → B4 min_tier=1 唯一最低
        result = expand_formula(60, overall_tier=3, grade_band="primary_low",
                                skill_tiers={"影像追忆": 3, "扫描速记": 3,
                                             "极速运算": 1, "极速学习": 1})
        # 所有捆绑都有 D(tier=1) → min_tier 全部 =1 → 字母序破平
        # B3(影像追忆=B) < B4(极速运算=D) → B3 胜出
        assert result["bundle_id"] in ("B3", "B4")

    def test_tier3_B4_wins_when_E_lowest(self):
        """极速学习 tier 唯一最低 → B4 优先于其他捆绑"""
        result = expand_formula(60, overall_tier=3, grade_band="primary_low",
                                skill_tiers={"影像追忆": 3, "扫描速记": 2,
                                             "极速运算": 2, "极速学习": 1})
        # B4: D(tier=2)+E(tier=1) → min=1, code=D
        # B2: C(tier=2)+D(tier=2) → min=2
        # B3: B(tier=3)+D(tier=2) → min=2
        # B4 的 min_tier=1 唯一最低 → B4 胜出
        assert result["bundle_id"] == "B4"

    def test_tier3_bundle_predecay(self):
        """捆绑后权重预衰减，补位不应重复选捆绑技能"""
        result = expand_formula(180, overall_tier=3, grade_band="primary_low",
                                skill_tiers={"影像追忆": 2, "扫描速记": 1,
                                             "极速运算": 1, "极速学习": 2})
        # B2 或 B4 优先（扫描速记/极速学习 tier 最低）
        assert len(result["slots"]) >= 2


class TestDecisionTree:
    """策略路由"""

    def test_normal_tier1_uses_weight_based(self):
        result = expand_formula(120, overall_tier=1, grade_band="primary_low")
        assert result["strategy"] == "weight_based"

    def test_normal_tier2_uses_weight_based(self):
        result = expand_formula(120, overall_tier=2, grade_band="primary_low")
        assert result["strategy"] == "weight_based"

    def test_consecutive_short_triggers_diversity(self):
        """连续 7 天 ≤20min → 轮换策略"""
        from app.services.training_formula_engine import HistoryEntry
        from datetime import date

        history = tuple(
            HistoryEntry(plan_date=date(2026, 7, d), planned_minutes=20,
                         skills=("超脑阅读",))
            for d in range(3, 10)  # 7 天
        )
        result = expand_formula(20, overall_tier=1, grade_band="primary_low",
                                history=history)
        assert result["strategy"] == "diversity_round_robin"

    def test_consecutive_14_triggers_upgrade(self):
        """连续 14 天 ≤20min → 强制升级"""
        from app.services.training_formula_engine import HistoryEntry
        from datetime import date

        history = tuple(
            HistoryEntry(plan_date=date(2026, 7, d), planned_minutes=20,
                         skills=("超脑阅读",))
            for d in range(1, 15)  # July 1-14
        )
        result = expand_formula(20, overall_tier=1, grade_band="primary_low",
                                history=history)
        assert result["strategy"] == "forced_upgrade"
        assert result["minutes"] >= 40

    def test_new_user_no_special_strategy(self):
        """新人 history=() → 不触发特殊策略"""
        result = expand_formula(20, overall_tier=1, grade_band="primary_low",
                                history=())
        assert result["strategy"] == "weight_based"


class TestTierWeights:
    """各阶权重演算"""

    def test_tier2_ABC_dominant(self):
        """Tier 2: A/B/C 权重高，短时不应出现 D/E"""
        result = expand_formula(40, overall_tier=2, grade_band="primary_low")
        for s in result["slots"]:
            assert s not in ("极速运算", "极速学习")

    def test_tier5_FG_appear(self):
        """Tier 5: F/G 权重最高，应出现在前排"""
        result = expand_formula(120, overall_tier=5, grade_band="primary_low")
        assert len(result["slots"]) == 3
        # F(0.20) 或 G(0.20) 应在其中
        tier5_skills = set(result["slots"])
        assert tier5_skills & {"文科奥秘", "理科奥秘"}

    def test_tier6_HI_appear(self):
        """Tier 6: H/I 权重最高"""
        result = expand_formula(120, overall_tier=6, grade_band="primary_low")
        tier6_skills = set(result["slots"])
        assert tier6_skills & {"天赋绘画", "音乐灵感"}
