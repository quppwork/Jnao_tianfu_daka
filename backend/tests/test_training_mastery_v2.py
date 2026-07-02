"""v2.0 晋级判定测试 — 打卡卡片 → 达标/计数/晋级"""

import pytest
from app.services.training_mastery import (
    evaluate_card,
    evaluate_skill_any_card,
    get_skill_threshold,
    _grade_band,
)


class TestGradeBand:
    """学段判定"""

    def test_primary_low(self):
        assert _grade_band("一年级") == "primary_low"
        assert _grade_band("三年级") == "primary_low"

    def test_primary_high(self):
        assert _grade_band("四年级") == "primary_high"
        assert _grade_band("六年级") == "primary_high"

    def test_junior(self):
        assert _grade_band("初一") == "junior"
        assert _grade_band("初三") == "junior"

    def test_senior(self):
        assert _grade_band("高一") == "senior"
        assert _grade_band("高三") == "senior"

    def test_unknown_returns_none(self):
        assert _grade_band("幼儿园") is None
        assert _grade_band("") is None
        assert _grade_band(None) is None


class TestGetThreshold:
    """阈值查找"""

    def test_speed_reading_tier1_primary_low(self):
        t = get_skill_threshold("超脑阅读", 1, "primary_low")
        assert t is not None
        assert t["type"] == "wpm"
        assert t["words"] == 800

    def test_recall_tier1_junior(self):
        t = get_skill_threshold("影像追忆", 1, "junior")
        assert t["type"] == "recall"
        assert t["words"] == 5000
        assert t["accuracy_pct"] == 80

    def test_scan_tier1_null(self):
        """Tier 1 扫描速记返回 None（练但不考）"""
        t = get_skill_threshold("扫描速记", 1, "primary_low")
        assert t is None

    def test_scan_tier2_not_null(self):
        t = get_skill_threshold("扫描速记", 2, "primary_low")
        assert t is not None
        assert t["type"] == "memory"

    def test_calc_tier1_null(self):
        t = get_skill_threshold("极速运算", 1, "primary_low")
        assert t is None

    def test_unknown_skill_returns_none(self):
        t = get_skill_threshold("不存在的技能", 1, "primary_low")
        assert t is None


class TestEvaluateCardWPM:
    """超脑阅读：字/分钟判定"""

    def test_pass_800w_3min(self):
        card = {"name": "超脑阅读", "time": "3", "wordCount": "800"}
        result = evaluate_card("超脑阅读", 1, "primary_low", card)
        assert result["passed"] is True
        assert result["wpm"] >= 266

    def test_pass_1000w_3min(self):
        card = {"name": "超脑阅读", "time": "2.5", "wordCount": "1000"}
        result = evaluate_card("超脑阅读", 1, "primary_low", card)
        assert result["passed"] is True

    def test_fail_500w_3min(self):
        card = {"name": "超脑阅读", "time": "3", "wordCount": "500"}
        result = evaluate_card("超脑阅读", 1, "primary_low", card)
        assert result["passed"] is False

    def test_missing_fields(self):
        card = {"name": "超脑阅读"}
        result = evaluate_card("超脑阅读", 1, "primary_low", card)
        assert result["passed"] is False
        assert "请填写" in result["detail"]

    def test_tier2_higher_threshold(self):
        """Tier 2: 2000字/5分钟 = 400wpm"""
        card = {"name": "超脑阅读", "time": "5", "wordCount": "2000"}
        result = evaluate_card("超脑阅读", 2, "primary_low", card)
        assert result["passed"] is True

    def test_tier2_fail_same_card(self):
        """Tier 1 达标的卡在 Tier 2 可能不达标"""
        card = {"name": "超脑阅读", "time": "3", "wordCount": "800"}
        result = evaluate_card("超脑阅读", 2, "primary_low", card)
        # 800/3 = 267wpm < 400wpm
        assert result["passed"] is False


class TestEvaluateCardRecall:
    """影像追忆：字数+准确度判定"""

    def test_pass(self):
        card = {"name": "影像追忆", "wordCount": "1500", "accuracy": "75"}
        result = evaluate_card("影像追忆", 1, "primary_low", card)
        assert result["passed"] is True

    def test_fail_low_accuracy(self):
        card = {"name": "影像追忆", "wordCount": "1500", "accuracy": "50"}
        result = evaluate_card("影像追忆", 1, "primary_low", card)
        assert result["passed"] is False

    def test_fail_low_words(self):
        card = {"name": "影像追忆", "wordCount": "500", "accuracy": "80"}
        result = evaluate_card("影像追忆", 1, "primary_low", card)
        assert result["passed"] is False

    def test_junior_higher(self):
        card = {"name": "影像追忆", "wordCount": "5000", "accuracy": "80"}
        result = evaluate_card("影像追忆", 1, "junior", card)
        assert result["passed"] is True

    def test_junior_fail(self):
        card = {"name": "影像追忆", "wordCount": "2000", "accuracy": "80"}
        result = evaluate_card("影像追忆", 1, "junior", card)
        assert result["passed"] is False


class TestEvaluateCardMemory:
    """扫描速记：字/分钟+倒背"""

    def test_pass_with_reverse(self):
        card = {"name": "扫描速记", "wordCount": "80", "time": "1", "reverseRecite": True}
        result = evaluate_card("扫描速记", 2, "primary_low", card)
        assert result["passed"] is True

    def test_fail_no_reverse(self):
        card = {"name": "扫描速记", "wordCount": "80", "time": "1", "reverseRecite": False}
        result = evaluate_card("扫描速记", 2, "primary_low", card)
        assert result["passed"] is False

    def test_fail_low_wpm(self):
        card = {"name": "扫描速记", "wordCount": "40", "time": "1", "reverseRecite": True}
        result = evaluate_card("扫描速记", 2, "primary_low", card)
        assert result["passed"] is False

    def test_tier4_higher(self):
        """Tier 4: 250字/分钟"""
        card = {"name": "扫描速记", "wordCount": "250", "time": "1", "reverseRecite": True}
        result = evaluate_card("扫描速记", 4, "primary_low", card)
        assert result["passed"] is True


class TestEvaluateCardSpeedCalc:
    """极速运算：完成判定"""

    def test_pass_completed(self):
        card = {"name": "极速运算", "completed": True}
        result = evaluate_card("极速运算", 3, "primary_low", card)
        assert result["passed"] is True

    def test_pass_correct_count(self):
        card = {"name": "极速运算", "correctCount": 8}
        result = evaluate_card("极速运算", 3, "primary_low", card)
        assert result["passed"] is True

    def test_fail_not_completed(self):
        card = {"name": "极速运算"}
        result = evaluate_card("极速运算", 3, "primary_low", card)
        assert result["passed"] is False


class TestEvaluateCardNullThreshold:
    """无阈值→默认通过"""

    def test_scan_tier1_passes(self):
        """扫描速记 Tier 1: 阈值 null，不考但通过（推进OSS）"""
        card = {"name": "扫描速记", "wordCount": "10"}
        result = evaluate_card("扫描速记", 1, "primary_low", card)
        assert result["passed"] is True

    def test_unknown_skill_passes(self):
        card = {"name": "未知技能"}
        result = evaluate_card("未知技能", 1, "primary_low", card)
        assert result["passed"] is True


class TestEvaluateSkillAnyCard:
    """多轮取优"""

    def test_first_pass_returns(self):
        cards = [
            {"name": "超脑阅读", "time": "3", "wordCount": "800"},
            {"name": "超脑阅读", "time": "3", "wordCount": "500"},
        ]
        result = evaluate_skill_any_card("超脑阅读", 1, "primary_low", cards)
        assert result["passed"] is True

    def test_no_cards_returns_fail(self):
        result = evaluate_skill_any_card("超脑阅读", 1, "primary_low", [])
        assert result["passed"] is False

    def test_all_fail_returns_fail_with_detail(self):
        cards = [
            {"name": "超脑阅读", "time": "3", "wordCount": "100"},
        ]
        result = evaluate_skill_any_card("超脑阅读", 1, "primary_low", cards)
        assert result["passed"] is False
        assert "未达标" in result["detail"]


class TestAdvanceFlowSimulation:
    """完整晋级流程模拟（纯函数验证，不涉及 DB）"""

    def test_three_consecutive_passes(self):
        """3次连续达标→Tier 晋级判断"""
        # Day 1: pass
        r1 = evaluate_card("超脑阅读", 1, "primary_low",
                           {"name": "超脑阅读", "time": "2.5", "wordCount": "800"})
        assert r1["passed"] is True

        # Day 2: pass
        r2 = evaluate_card("超脑阅读", 1, "primary_low",
                           {"name": "超脑阅读", "time": "2", "wordCount": "800"})
        assert r2["passed"] is True

        # Day 3: pass → should trigger advance
        r3 = evaluate_card("超脑阅读", 1, "primary_low",
                           {"name": "超脑阅读", "time": "1.5", "wordCount": "800"})
        assert r3["passed"] is True
        # After 3 passes, tier should go from 1→2

    def test_break_on_fail(self):
        """达标→达标→不达标：第3天中断"""
        r1 = evaluate_card("超脑阅读", 1, "primary_low",
                           {"name": "超脑阅读", "time": "2.5", "wordCount": "800"})
        assert r1["passed"] is True

        r2 = evaluate_card("超脑阅读", 1, "primary_low",
                           {"name": "超脑阅读", "time": "2", "wordCount": "800"})
        assert r2["passed"] is True

        r3 = evaluate_card("超脑阅读", 1, "primary_low",
                           {"name": "超脑阅读", "time": "3", "wordCount": "100"})
        assert r3["passed"] is False
        # Count should reset, no advance

    def test_tier_threshold_escalation(self):
        """Tier 升级后阈值变高，旧水平不再达标"""
        # Tier 1 pass: 800字/3min = 267wpm ≥ 267wpm ✓
        r = evaluate_card("超脑阅读", 1, "primary_low",
                          {"name": "超脑阅读", "time": "3", "wordCount": "800"})
        assert r["passed"] is True

        # Same card at Tier 2: 800/3 = 267wpm < 400wpm ✗
        r = evaluate_card("超脑阅读", 2, "primary_low",
                          {"name": "超脑阅读", "time": "3", "wordCount": "800"})
        assert r["passed"] is False
