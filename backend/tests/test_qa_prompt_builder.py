"""学科答疑 Prompt 构建 — 学段 + 天赋画像"""

from app.services.qa_prompt_builder import (
    build_qa_system_prompt,
    infer_school_stage,
    talent_coaching_hint,
)


class TestSchoolStage:
    def test_infer_primary_low(self):
        assert infer_school_stage(grade="二年级", age=8) == "primary_low"

    def test_infer_junior(self):
        assert infer_school_stage(grade="初一", age=13) == "junior"

    def test_infer_from_age_only(self):
        assert infer_school_stage(grade=None, age=15) == "junior"


class TestTalentCoaching:
    def test_sizhe_overthink_hint(self):
        hint = talent_coaching_hint("思者", report_json={"results": {"State": {"name": "相争"}}})
        assert "想太多" in hint or "分析" in hint

    def test_xingzhe_action_hint(self):
        hint = talent_coaching_hint("行者")
        assert "动手" in hint or "试" in hint


class TestBuildPrompt:
    def test_primary_low_language(self):
        prompt = build_qa_system_prompt(
            school_stage="primary_low",
            grade="二年级",
            talent_primary="学者",
        )
        assert "小学低" in prompt or "短句" in prompt
        assert "学者" in prompt

    def test_includes_subject(self):
        prompt = build_qa_system_prompt(subject="数学", talent_primary="赢者")
        assert "数学" in prompt
