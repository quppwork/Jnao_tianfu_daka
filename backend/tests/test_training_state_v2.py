"""v2.0 状态机单元测试 — 多技能 Tier + OSS + 连续计数"""

import pytest
from app.services.child_training_state import (
    _default_state,
    REQUIRED_SKILLS,
    overall_tier,
    get_skill_state,
    get_skill_tier,
    get_skill_oss_position,
    get_consecutive_pass,
    set_skill_tier,
    set_skill_oss_position,
    set_consecutive_pass,
    bump_consecutive_pass,
    reset_consecutive_pass,
    advance_skill_tier,
    bump_training_completed_day,
    training_day_number,
    state_summary,
)


class TestDefaultState:
    """新用户初始化"""

    def test_all_five_skills_present(self):
        state = _default_state()
        for sk in REQUIRED_SKILLS:
            assert sk in state["skills"]

    def test_all_tier_one(self):
        state = _default_state()
        for sk in REQUIRED_SKILLS:
            assert state["skills"][sk]["tier"] == 1

    def test_all_consecutive_pass_zero(self):
        state = _default_state()
        for sk in REQUIRED_SKILLS:
            assert state["skills"][sk]["consecutive_pass"] == 0

    def test_default_oss_positions(self):
        state = _default_state()
        assert state["skills"]["超脑阅读"]["oss_stage"] == 0
        assert state["skills"]["超脑阅读"]["oss_part"] == 0
        assert state["skills"]["影像追忆"]["oss_stage"] == 1
        assert state["skills"]["影像追忆"]["oss_part"] == 1
        assert state["skills"]["极速运算"]["oss_stage"] == 2
        assert state["skills"]["极速学习"]["oss_stage"] == 2

    def test_talent_diff_speed_learning(self):
        """行者/德者极速学习从 stage 3 开始"""
        state_xuezhe = _default_state(talent_code=1)
        state_xingzhe = _default_state(talent_code=3)
        state_dezhe = _default_state(talent_code=4)
        state_sizhe = _default_state(talent_code=2)
        state_yingzhe = _default_state(talent_code=5)

        assert state_xuezhe["skills"]["极速学习"]["oss_stage"] == 2
        assert state_sizhe["skills"]["极速学习"]["oss_stage"] == 2
        assert state_yingzhe["skills"]["极速学习"]["oss_stage"] == 2
        assert state_xingzhe["skills"]["极速学习"]["oss_stage"] == 3
        assert state_dezhe["skills"]["极速学习"]["oss_stage"] == 3

    def test_training_days_zero(self):
        state = _default_state()
        assert state["training_days"] == 0
        assert state["training_day_anchor"] is None
        assert state["last_settled_plan_date"] is None


class TestOverallTier:
    """整体 Tier = 最低原则"""

    def test_all_one_returns_one(self):
        state = _default_state()
        assert overall_tier(state) == 1

    def test_one_advanced_others_one(self):
        state = _default_state()
        state["skills"]["超脑阅读"]["tier"] = 5
        state["skills"]["影像追忆"]["tier"] = 2
        # 扫描速记/极速运算/极速学习 still tier 1
        assert overall_tier(state) == 1  # min = 1

    def test_all_three_returns_three(self):
        state = _default_state()
        for sk in REQUIRED_SKILLS:
            state["skills"][sk]["tier"] = 3
        assert overall_tier(state) == 3

    def test_empty_skills_defaults_one(self):
        assert overall_tier({"skills": {}}) == 1


class TestConsecutivePass:
    """连续达标计数"""

    def test_starts_zero(self):
        state = _default_state()
        assert get_consecutive_pass(state, "影像追忆") == 0

    def test_bump_increments(self):
        state = _default_state()
        assert bump_consecutive_pass(state, "影像追忆") == 1
        assert bump_consecutive_pass(state, "影像追忆") == 2
        assert bump_consecutive_pass(state, "影像追忆") == 3
        assert get_consecutive_pass(state, "影像追忆") == 3

    def test_reset_zeroes(self):
        state = _default_state()
        bump_consecutive_pass(state, "影像追忆")
        bump_consecutive_pass(state, "影像追忆")
        reset_consecutive_pass(state, "影像追忆")
        assert get_consecutive_pass(state, "影像追忆") == 0

    def test_set_manual_count(self):
        state = _default_state()
        set_consecutive_pass(state, "超脑阅读", 5)
        assert get_consecutive_pass(state, "超脑阅读") == 5

    def test_set_negative_clamped(self):
        state = _default_state()
        set_consecutive_pass(state, "超脑阅读", -3)
        assert get_consecutive_pass(state, "超脑阅读") == 0

    def test_skills_independent(self):
        """各技能计数独立"""
        state = _default_state()
        bump_consecutive_pass(state, "影像追忆")
        bump_consecutive_pass(state, "影像追忆")
        bump_consecutive_pass(state, "超脑阅读")
        assert get_consecutive_pass(state, "影像追忆") == 2
        assert get_consecutive_pass(state, "超脑阅读") == 1


class TestTierAdvance:
    """Tier 晋级"""

    def test_advance_from_one_to_two(self):
        state = _default_state()
        for _ in range(3):
            bump_consecutive_pass(state, "影像追忆")
        new_tier = advance_skill_tier(state, "影像追忆")
        assert new_tier == 2
        assert get_skill_tier(state, "影像追忆") == 2

    def test_advance_resets_consecutive_pass(self):
        state = _default_state()
        for _ in range(3):
            bump_consecutive_pass(state, "影像追忆")
        advance_skill_tier(state, "影像追忆")
        assert get_consecutive_pass(state, "影像追忆") == 0

    def test_manual_set_tier(self):
        state = _default_state()
        set_skill_tier(state, "超脑阅读", 4)
        assert get_skill_tier(state, "超脑阅读") == 4

    def test_other_skills_unaffected(self):
        """晋级一个技能不影响其他"""
        state = _default_state()
        for _ in range(3):
            bump_consecutive_pass(state, "影像追忆")
        advance_skill_tier(state, "影像追忆")
        assert get_skill_tier(state, "扫描速记") == 1
        assert get_skill_tier(state, "超脑阅读") == 1


class TestOSSPosition:
    """OSS stage/part 读写"""

    def test_default_read(self):
        state = _default_state()
        assert get_skill_oss_position(state, "影像追忆") == (1, 1)
        assert get_skill_oss_position(state, "超脑阅读") == (0, 0)

    def test_write_and_read(self):
        state = _default_state()
        set_skill_oss_position(state, "影像追忆", 3, 2)
        assert get_skill_oss_position(state, "影像追忆") == (3, 2)

    def test_new_skill_defaults(self):
        """不存在的技能返回默认值"""
        state = _default_state()
        sd = get_skill_state(state, "不存在的技能")
        assert sd["tier"] == 1
        assert sd["consecutive_pass"] == 0


class TestTrainingDays:
    """训练日"""

    def test_day_number_unbumped(self):
        state = _default_state()
        assert training_day_number(state) == 1  # 0 + 1

    def test_bump_first_day(self):
        state = _default_state()
        bump_training_completed_day(state)
        assert state["training_days"] == 1
        assert training_day_number(state) == 2

    def test_bump_multiple_days(self):
        state = _default_state()
        for _ in range(10):
            bump_training_completed_day(state)
        assert state["training_days"] == 10
        assert training_day_number(state) == 11


class TestStateSummary:
    """API 返回摘要"""

    def test_contains_overall_tier(self):
        state = _default_state()
        summary = state_summary(state)
        assert summary["overall_tier"] == 1

    def test_contains_all_five_skills(self):
        state = _default_state()
        summary = state_summary(state)
        assert len(summary["skills"]) == 5
        for sk in REQUIRED_SKILLS:
            assert sk in summary["skills"]
            assert "tier" in summary["skills"][sk]
            assert "oss_stage" in summary["skills"][sk]
            assert "oss_part" in summary["skills"][sk]
            assert "consecutive_pass" in summary["skills"][sk]

    def test_contains_training_days(self):
        state = _default_state()
        bump_training_completed_day(state)
        summary = state_summary(state)
        assert summary["training_days"] == 1

    def test_overall_tier_reflects_min(self):
        state = _default_state()
        state["skills"]["超脑阅读"]["tier"] = 5
        state["skills"]["影像追忆"]["tier"] = 3
        summary = state_summary(state)
        assert summary["overall_tier"] == 1  # 扫描速记 still tier 1


class TestConsecutivePassFlow:
    """模拟连续达标→晋级的完整流程"""

    def test_full_advance_flow(self):
        """模拟影像追忆连续3次达标→Tier+1"""
        state = _default_state()

        # Day 1: 达标
        bump_consecutive_pass(state, "影像追忆")
        assert get_consecutive_pass(state, "影像追忆") == 1
        assert get_skill_tier(state, "影像追忆") == 1

        # Day 2: 达标
        bump_consecutive_pass(state, "影像追忆")
        assert get_consecutive_pass(state, "影像追忆") == 2

        # Day 3: 达标 → Tier 晋级
        bump_consecutive_pass(state, "影像追忆")
        assert get_consecutive_pass(state, "影像追忆") == 3
        new_tier = advance_skill_tier(state, "影像追忆")
        assert new_tier == 2
        assert get_consecutive_pass(state, "影像追忆") == 0

    def test_break_on_fail(self):
        """不达标→中断，计数重置"""
        state = _default_state()

        bump_consecutive_pass(state, "影像追忆")  # 1
        bump_consecutive_pass(state, "影像追忆")  # 2
        reset_consecutive_pass(state, "影像追忆")  # 不达标！
        assert get_consecutive_pass(state, "影像追忆") == 0

        # 重新开始
        bump_consecutive_pass(state, "影像追忆")  # 1
        assert get_consecutive_pass(state, "影像追忆") == 1
