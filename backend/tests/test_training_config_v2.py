"""v2.0 配置加载单元测试 — YAML 配置正确性"""

import pytest
from config.loader import load_training_curriculum, load_training_tier_thresholds


class TestCurriculumV2:
    """training_curriculum.yaml v2.0"""

    def test_version_two(self):
        cur = load_training_curriculum()
        assert cur["version"] == 2

    def test_five_required_skills(self):
        cur = load_training_curriculum()
        assert len(cur["skills"]["required"]) == 5
        assert "超脑阅读" in cur["skills"]["required"]
        assert "影像追忆" in cur["skills"]["required"]
        assert "扫描速记" in cur["skills"]["required"]
        assert "极速运算" in cur["skills"]["required"]
        assert "极速学习" in cur["skills"]["required"]

    def test_three_elective_skills(self):
        cur = load_training_curriculum()
        assert len(cur["skills"]["elective"]) == 3
        assert "精力恢复" in cur["skills"]["elective"]
        assert "多元感知" in cur["skills"]["elective"]
        assert "高效作业" in cur["skills"]["elective"]

    def test_six_duration_slots(self):
        cur = load_training_curriculum()
        assert len(cur["duration_formula"]) == 6

    def test_duration_20min(self):
        cur = load_training_curriculum()
        slot = cur["duration_formula"][0]
        assert slot["minutes"] == 20
        assert slot["slots"] == ["A"]

    def test_duration_40min(self):
        cur = load_training_curriculum()
        slot = cur["duration_formula"][1]
        assert slot["minutes"] == 40
        assert slot["slots"] == ["A", "B"]

    def test_duration_60_120min_has_c_note(self):
        cur = load_training_curriculum()
        slot = cur["duration_formula"][2]
        assert slot["minutes"] == [60, 120]
        assert "C" in slot["primary_school"]
        assert slot["junior_high_c_note"] == "不建议"

    def test_duration_121_180min_has_tier_replace(self):
        cur = load_training_curriculum()
        slot = cur["duration_formula"][3]
        assert "tier_replace" in slot
        assert slot["tier_replace"]["高效作业"] == "极速学习"
        assert "2B" in str(slot["primary_school"]) or slot["primary_school"].count("B") == 2

    def test_slot_mapping_all_five(self):
        cur = load_training_curriculum()
        sm = cur["slot_mapping"]
        assert sm["A"] == "超脑阅读"
        assert sm["B"] == "影像追忆"
        assert sm["C"] == "扫描速记"
        assert sm["D"] == "极速运算"
        assert sm["E"] == "极速学习"

    def test_elective_rules_defined(self):
        cur = load_training_curriculum()
        er = cur["elective_rules"]
        assert "精力恢复" in er
        assert "多元感知" in er
        assert "高效作业" in er
        assert er["高效作业"]["blocks_next"] is False
        assert er["高效作业"]["has_checkin"] is False
        assert er["多元感知"]["has_checkin"] is True

    def test_grade_behavior_junior_c(self):
        cur = load_training_curriculum()
        gb = cur["grade_behavior"]
        assert gb["junior_high_c"] == "not_recommended"

    def test_scope_current_tier_one(self):
        cur = load_training_curriculum()
        assert cur["scope"]["current_tier_formulas"] == [1]
        assert cur["scope"]["exclude_tiers"] == [6, 7, 8, 9]

    def test_training_day_cutoff(self):
        cur = load_training_curriculum()
        assert cur["training_day"]["cutoff_hour"] == 4


class TestTierThresholds:
    """training_tier_thresholds.yaml"""

    def test_advance_rules(self):
        th = load_training_tier_thresholds()
        ar = th["advance_rule"]
        assert ar["consecutive_pass"] == 3
        assert ar["reset_on_fail"] is True
        assert ar["per_skill_independent"] is True

    def test_six_skills_configured(self):
        th = load_training_tier_thresholds()
        assert len(th["tier_thresholds"]) == 6

    def test_grade_bands_four_levels(self):
        th = load_training_tier_thresholds()
        assert len(th["grade_bands"]) == 4

    # ── 超脑阅读 ──

    def test_speed_reading_tier1_primary_low(self):
        th = load_training_tier_thresholds()
        t = th["tier_thresholds"]["超脑阅读"][1]["primary_low"]
        assert t["type"] == "wpm"
        assert t["words"] == 800
        assert t["minutes"] == 3

    def test_speed_reading_tier1_junior(self):
        th = load_training_tier_thresholds()
        t = th["tier_thresholds"]["超脑阅读"][1]["junior"]
        assert t["words"] == 1800

    def test_speed_reading_tier2_primary_low(self):
        th = load_training_tier_thresholds()
        t = th["tier_thresholds"]["超脑阅读"][2]["primary_low"]
        assert t["words"] == 2000
        assert t["minutes"] == 5

    # ── 影像追忆 ──

    def test_recall_tier1_primary_low(self):
        th = load_training_tier_thresholds()
        t = th["tier_thresholds"]["影像追忆"][1]["primary_low"]
        assert t["type"] == "recall"
        assert t["words"] == 1500
        assert t["accuracy_pct"] == 75

    def test_recall_tier2_senior(self):
        th = load_training_tier_thresholds()
        t = th["tier_thresholds"]["影像追忆"][2]["senior"]
        assert t["words"] == 7000
        assert t["accuracy_pct"] == 85

    def test_recall_has_five_tiers(self):
        th = load_training_tier_thresholds()
        assert set(th["tier_thresholds"]["影像追忆"].keys()) == {1, 2, 3, 4, 5}

    # ── 扫描速记 ──

    def test_scan_tier1_is_null(self):
        """Tier 1 练但不考"""
        th = load_training_tier_thresholds()
        assert th["tier_thresholds"]["扫描速记"][1]["primary_low"] is None
        assert th["tier_thresholds"]["扫描速记"][1]["junior"] is None

    def test_scan_tier2_primary_low(self):
        th = load_training_tier_thresholds()
        t = th["tier_thresholds"]["扫描速记"][2]["primary_low"]
        assert t["type"] == "memory"
        assert t["words_per_min"] == 80
        assert t["reverse_recite"] is True

    def test_scan_tier2_junior(self):
        th = load_training_tier_thresholds()
        t = th["tier_thresholds"]["扫描速记"][2]["junior"]
        assert t["words_per_min"] == 80

    # ── 极速运算 ──

    def test_calc_tier1_2_are_null(self):
        th = load_training_tier_thresholds()
        assert th["tier_thresholds"]["极速运算"][1]["primary_low"] is None
        assert th["tier_thresholds"]["极速运算"][2]["primary_low"] is None

    def test_calc_tier3_primary_low(self):
        th = load_training_tier_thresholds()
        t = th["tier_thresholds"]["极速运算"][3]["primary_low"]
        assert t["type"] == "speed_calc"
        assert t["digits"] == [5, 5]

    def test_calc_tier3_junior_optional(self):
        th = load_training_tier_thresholds()
        t = th["tier_thresholds"]["极速运算"][3]["junior"]
        assert t["optional"] is True

    # ── 极速学习 ──

    def test_speed_learn_tier1_3_null(self):
        th = load_training_tier_thresholds()
        for t in [1, 2, 3]:
            assert th["tier_thresholds"]["极速学习"][t]["all"] is None

    def test_speed_learn_tier4(self):
        th = load_training_tier_thresholds()
        t = th["tier_thresholds"]["极速学习"][4]["primary_low"]
        assert t["type"] == "program"
        assert t["days"] == 5

    # ── 高效作业 ──

    def test_homework_tier1_null(self):
        th = load_training_tier_thresholds()
        assert th["tier_thresholds"]["高效作业"][1]["primary_low"] is None

    # ── 宽容策略 ──

    def test_scan_tolerance(self):
        th = load_training_tier_thresholds()
        st = th["scan_memory_tolerance"]
        assert st["strict_mode"] is False
        assert st["reverse_recite_check"] == "sample"
