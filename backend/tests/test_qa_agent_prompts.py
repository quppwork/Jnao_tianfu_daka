"""QA Agent 分频道提示词测试"""

from app.agents.qa.prompt_builder import build_learner_context_block, build_qa_system_prompt
from app.agents.qa.subjects.registry import get_subject_agent


class TestSubjectAgents:
    def test_math_agent_has_role_and_style(self):
        agent = get_subject_agent("理科")
        assert agent is not None
        assert "理科" in agent.role_prompt
        assert "审题" in agent.answer_style
        assert agent.soft_constraint
        assert "硬约束" in agent.hard_constraint

    def test_legacy_alias_resolves(self):
        assert get_subject_agent("数学") is get_subject_agent("理科")

    def test_chinese_agent_covers_reading_and_writing(self):
        agent = get_subject_agent("文科")
        assert "阅读" in agent.role_prompt or "阅读" in agent.answer_style
        assert "作文" in agent.role_prompt or "作文" in agent.answer_style

    def test_english_agent_covers_grammar(self):
        agent = get_subject_agent("外语")
        assert "语法" in agent.role_prompt or "grammar" in agent.role_prompt.lower()
        assert "原文" in agent.answer_style
        assert "词：" in agent.answer_style
        assert "只精讲" in agent.answer_style or "一题" in agent.answer_style
        assert "软约束" in (agent.soft_constraint or "")
        assert "原文" in (agent.soft_constraint or "")

    def test_prompt_includes_one_question_pace(self):
        prompt = build_qa_system_prompt(subject="外语", school_stage="junior")
        assert "多题节奏" in prompt
        assert "只精讲" in prompt
        assert "禁止写成 Q28" in prompt or "勿写 Q28" in prompt
        assert "谢谢你点名" in prompt or "多轮顺接" in prompt


class TestBuildPromptBySubject:
    def test_math_prompt_includes_channel_and_soft(self):
        prompt = build_qa_system_prompt(subject="理科", school_stage="junior")
        assert "张宇老师" in prompt or "余峰" in prompt
        assert "理科" in prompt
        assert "软约束" in prompt
        assert "初中" in prompt
        learner = build_learner_context_block(talent_primary="学者")
        assert "学者" in learner

    def test_chinese_prompt_includes_evidence_rule(self):
        prompt = build_qa_system_prompt(subject="文科", school_stage="primary_high")
        assert "文科" in prompt
        assert "依据" in prompt or "原文" in prompt

    def test_english_prompt_includes_examples_rule(self):
        prompt = build_qa_system_prompt(subject="外语", school_stage="senior")
        assert "外语" in prompt
        assert "例句" in prompt or "例" in prompt
        assert "原文" in prompt
        assert "词：" in prompt
