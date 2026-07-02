"""v2.0 公式引擎测试 — 时长 → 技能组合"""

import pytest
from app.services.training_formula_engine import expand_formula, _apply_tier_replace


class TestFormulaEngine:
    """时长公式展开"""

    def test_20min_returns_A_only(self):
        result = expand_formula(20, overall_tier=1, grade_band="primary_low")
        assert result["slots"] == ["超脑阅读"]
        assert result["c_note"] is None

    def test_40min_returns_A_B(self):
        result = expand_formula(40, overall_tier=1, grade_band="primary_low")
        assert result["slots"] == ["超脑阅读", "影像追忆"]

    def test_90min_primary_returns_A_B_C(self):
        result = expand_formula(90, overall_tier=1, grade_band="primary_low")
        assert "超脑阅读" in result["slots"]
        assert "影像追忆" in result["slots"]
        assert "扫描速记" in result["slots"]

    def test_120min_primary_returns_A_B_C(self):
        """120min 落在 [60,120] 档，恰好边界"""
        result = expand_formula(120, overall_tier=1, grade_band="primary_low")
        assert "超脑阅读" in result["slots"]
        assert "影像追忆" in result["slots"]
        assert "扫描速记" in result["slots"]

    def test_121min_primary_returns_2B(self):
        """121min 落在 [121,180] 档，2B"""
        result = expand_formula(121, overall_tier=1, grade_band="primary_low")
        b_count = result["slots"].count("影像追忆")
        assert b_count == 2, f"Expected 2B, got {b_count}"

    def test_180min_primary_returns_2B_homework(self):
        result = expand_formula(150, overall_tier=1, grade_band="primary_low")
        assert "高效作业" in result["slots"]
        assert result["slots"].count("影像追忆") == 2

    def test_300min_primary_returns_3B(self):
        result = expand_formula(250, overall_tier=1, grade_band="primary_low")
        b_count = result["slots"].count("影像追忆")
        assert b_count == 3, f"Expected 3B, got {b_count}"

    def test_junior_high_c_not_recommended(self):
        result = expand_formula(90, overall_tier=1, grade_band="junior")
        assert result["c_note"] == "不建议"
        assert "扫描速记" in result["slots"]  # Still included

    def test_senior_c_not_recommended(self):
        result = expand_formula(90, overall_tier=1, grade_band="senior")
        assert result["c_note"] == "不建议"

    def test_tier_below_3_no_replace(self):
        """Tier 1: 不触发 高效作业→极速学习 替换"""
        result = expand_formula(150, overall_tier=1, grade_band="primary_low")
        assert "高效作业" in result["slots"]
        assert "极速学习" not in result["slots"]

    def test_tier_3_triggers_replace(self):
        """Tier 3: 触发替换"""
        result = expand_formula(150, overall_tier=3, grade_band="primary_low")
        assert "高效作业" not in result["slots"]
        assert "极速学习" in result["slots"]

    def test_tier_3_240min_2E(self):
        """3-4h Tier 3: 2E"""
        result = expand_formula(200, overall_tier=3, grade_band="primary_low")
        e_count = result["slots"].count("极速学习")
        assert e_count == 2, f"Expected 2E, got {e_count}"

    def test_tier_3_300min_3E(self):
        """4-5h Tier 3: 3E"""
        result = expand_formula(250, overall_tier=3, grade_band="primary_low")
        e_count = result["slots"].count("极速学习")
        assert e_count == 3, f"Expected 3E, got {e_count}"

    def test_elective_notes_homework(self):
        result = expand_formula(150, overall_tier=1, grade_band="primary_low")
        notes = {n["skill"]: n for n in result["elective_notes"]}
        assert "高效作业" in notes
        assert notes["高效作业"]["has_checkin"] is False
        assert notes["高效作业"]["blocks_next"] is False

    def test_exam_note_in_2_3h(self):
        result = expand_formula(150, overall_tier=1, grade_band="primary_low")
        assert result["exam_note"] is not None
        assert "试卷" in result["exam_note"]

    def test_fallback_matches_closest(self):
        """不精确匹配→最近高档位"""
        result = expand_formula(25, overall_tier=1, grade_band="primary_low")
        assert len(result["slots"]) > 0

    def test_primary_high_uses_same_formula(self):
        result = expand_formula(90, overall_tier=1, grade_band="primary_high")
        assert "扫描速记" in result["slots"]
        assert result["c_note"] is None  # C not marked for primary


class TestTierReplace:
    """≥3阶替换逻辑"""

    def test_no_replace_map(self):
        slots = ["A", "B", "C"]
        assert _apply_tier_replace(slots, {}) == ["A", "B", "C"]

    def test_single_replace(self):
        slots = ["A", "高效作业"]
        result = _apply_tier_replace(slots, {"高效作业": "极速学习"})
        assert result == ["A", "极速学习"]

    def test_list_expansion(self):
        slots = ["A", "高效作业"]
        result = _apply_tier_replace(slots, {"高效作业": ["极速学习", "极速学习"]})
        assert result == ["A", "极速学习", "极速学习"]

    def test_multiple_replace(self):
        slots = ["高效作业", "A", "高效作业"]
        result = _apply_tier_replace(slots, {"高效作业": "极速学习"})
        assert result == ["极速学习", "A", "极速学习"]
