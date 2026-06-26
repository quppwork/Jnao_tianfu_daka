"""QA Agent 分学科提示词测试"""

from app.agents.qa.prompt_builder import build_qa_system_prompt
from app.agents.qa.subjects.registry import get_subject_agent


class TestSubjectAgents:
    def test_math_agent_has_role_and_style(self):
        agent = get_subject_agent("数学")
        assert agent is not None
        assert "数学" in agent.role_prompt
        assert "分步" in agent.answer_style

    def test_chinese_agent_covers_reading_and_writing(self):
        agent = get_subject_agent("语文")
        assert "阅读" in agent.role_prompt or "阅读" in agent.answer_style
        assert "作文" in agent.role_prompt or "作文" in agent.answer_style

    def test_english_agent_covers_grammar(self):
        agent = get_subject_agent("英语")
        assert "语法" in agent.role_prompt or "grammar" in agent.role_prompt.lower()


class TestBuildPromptBySubject:
    def test_math_prompt_includes_zhangyu_and_math_style(self):
        prompt = build_qa_system_prompt(subject="数学", school_stage="junior", talent_primary="学者")
        assert "张宇老师" in prompt
        assert "数学" in prompt
        assert "学者" in prompt
        assert "初中" in prompt

    def test_chinese_prompt_includes_evidence_rule(self):
        prompt = build_qa_system_prompt(subject="语文", school_stage="primary_high")
        assert "语文" in prompt
        assert "依据" in prompt or "原文" in prompt

    def test_english_prompt_includes_examples_rule(self):
        prompt = build_qa_system_prompt(subject="英语", school_stage="senior")
        assert "英语" in prompt
        assert "例句" in prompt or "例" in prompt
