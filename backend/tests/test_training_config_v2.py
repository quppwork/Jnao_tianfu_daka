"""v3.0 配置加载单元测试 — YAML 配置正确性"""

import pytest
from config.loader import load_training_curriculum, load_training_tier_thresholds


class TestCurriculumV3:
    """training_curriculum.yaml v3.0"""

    def test_version_three(self):
        cur = load_training_curriculum()
        assert cur["version"] == 3

    # ── 技能定义 ──

    def test_nine_required_skills(self):
        cur = load_training_curriculum()
        assert len(cur["skills"]["required"]) == 9
        for skill in ("超脑阅读", "影像追忆", "扫描速记",
                      "极速运算", "极速学习",
                      "文科奥秘", "理科奥秘", "天赋绘画", "音乐灵感"):
            assert skill in cur["skills"]["required"]

    def test_three_elective_skills(self):
        cur = load_training_curriculum()
        assert len(cur["skills"]["elective"]) == 3
        for skill in ("精力恢复", "多元感知", "高效作业"):
            assert skill in cur["skills"]["elective"]

    # ── Decision Tree ──

    def test_decision_tree_has_root(self):
        cur = load_training_curriculum()
        tree = cur["decision_tree"]
        assert "root" in tree
        assert tree["root"] in tree["nodes"]

    def test_decision_tree_two_strategy_leaves(self):
        cur = load_training_curriculum()
        nodes = cur["decision_tree"]["nodes"]
        strategies = {v["strategy"] for v in nodes.values()
                      if v["type"] == "strategy"}
        assert strategies == {"weight_based", "weight_with_bundle"}

    def test_decision_tree_no_dead_ends(self):
        """所有条件节点都有 on_true/on_false 指向有效节点"""
        cur = load_training_curriculum()
        nodes = cur["decision_tree"]["nodes"]
        for name, node in nodes.items():
            if node["type"] == "condition":
                assert node["on_true"] in nodes, (
                    f"{name}.on_true={node['on_true']} 不存在"
                )
                assert node["on_false"] in nodes, (
                    f"{name}.on_false={node['on_false']} 不存在"
                )

    # ── 槽位表 ──

    def test_slot_table_has_six_entries(self):
        cur = load_training_curriculum()
        assert len(cur["slot_table"]) == 7  # 20/40/60-120/121-180/181-240/241-479/480+

    def test_slot_20min_is_1(self):
        cur = load_training_curriculum()
        assert cur["slot_table"][0]["slots"] == 1

    def test_slot_40min_is_2(self):
        cur = load_training_curriculum()
        assert cur["slot_table"][1]["slots"] == 2

    # ── 权重表 ──

    def test_tier_weights_all_sum_to_one(self):
        cur = load_training_curriculum()
        for tier_key, weights in cur["tier_weights"].items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.001, (
                f"{tier_key} sum={total}, expected 1.0"
            )

    def test_tier_weights_six_tiers(self):
        cur = load_training_curriculum()
        assert len(cur["tier_weights"]) == 6

    def test_tier5_has_FG(self):
        cur = load_training_curriculum()
        w = cur["tier_weights"]["tier_5"]
        assert "F" in w and "G" in w

    def test_tier6_has_HI(self):
        cur = load_training_curriculum()
        w = cur["tier_weights"]["tier_6"]
        assert "H" in w and "I" in w

    # ── 衰减规则 ──

    def test_decay_factors_valid(self):
        cur = load_training_curriculum()
        factors = cur["decay_rules"]["factors"]
        assert 0 < factors["key"] < 1
        assert 0 < factors["secondary"] < 1

    def test_decay_threshold_exists(self):
        cur = load_training_curriculum()
        assert cur["decay_rules"]["threshold"] > 0

    # ── 捆绑配置 ──

    def test_bundles_tier3_has_four(self):
        cur = load_training_curriculum()
        assert len(cur["bundles"]["tier_3"]) == 4

    def test_bundles_tier4_is_empty(self):
        cur = load_training_curriculum()
        assert cur["bundles"]["tier_4"] == []

    def test_bundle_B2_has_grade_note(self):
        cur = load_training_curriculum()
        b2 = [b for b in cur["bundles"]["tier_3"] if b["id"] == "B2"][0]
        assert b2["grade_note"]["junior"] == "不推荐"
        assert b2["grade_note"]["senior"] == "不推荐"

    # ── 学段标注 ──

    def test_grade_notes_junior(self):
        cur = load_training_curriculum()
        assert cur["grade_notes"]["junior"][0]["skill"] == "扫描速记"

    # ── 选修规则 ──

    def test_elective_rules_defined(self):
        cur = load_training_curriculum()
        er = cur["elective_rules"]
        assert "精力恢复" in er
        assert "多元感知" in er
        assert "高效作业" in er
        assert er["高效作业"]["blocks_next"] is False

    # ── 槽位映射 ──

    def test_slot_mapping_nine_skills(self):
        cur = load_training_curriculum()
        sm = cur["slot_mapping"]
        assert len(sm) == 9
        assert sm["F"] == "文科奥秘"
        assert sm["G"] == "理科奥秘"
        assert sm["H"] == "天赋绘画"
        assert sm["I"] == "音乐灵感"

    # ── 训练日 ──

    def test_training_day_cutoff(self):
        cur = load_training_curriculum()
        assert cur["training_day"]["cutoff_hour"] == 4

    # ── 版本范围 ──

    def test_scope_includes_all_tiers(self):
        cur = load_training_curriculum()
        assert 3 in cur["scope"]["current_tier_formulas"]
        assert 6 in cur["scope"]["current_tier_formulas"]


class TestTierThresholds:
    """training_tier_thresholds.yaml — 不变"""

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

    def test_speed_reading_tier1_primary_low(self):
        th = load_training_tier_thresholds()
        t = th["tier_thresholds"]["超脑阅读"][1]["primary_low"]
        assert t["type"] == "wpm"
        assert t["words"] == 800

    def test_recall_tier1_primary_low(self):
        th = load_training_tier_thresholds()
        t = th["tier_thresholds"]["影像追忆"][1]["primary_low"]
        assert t["type"] == "recall"
        assert t["accuracy_pct"] == 75

    def test_scan_tier1_is_null(self):
        th = load_training_tier_thresholds()
        assert th["tier_thresholds"]["扫描速记"][1]["primary_low"] is None

    def test_calc_tier3_primary_low(self):
        th = load_training_tier_thresholds()
        t = th["tier_thresholds"]["极速运算"][3]["primary_low"]
        assert t["type"] == "speed_calc"
