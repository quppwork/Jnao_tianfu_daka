import pytest
"""QA Agent 学科路由测试"""

from app.agents.qa.router import check_subject_mismatch, detect_subject, mismatch_reply


class TestDetectSubject:
    def test_math_fraction_question(self):
        subject, score = detect_subject("分数加法怎么算？分子分母不同怎么办？")
        assert subject == "数学"
        assert score >= 2

    def test_chinese_poetry_question(self):
        subject, score = detect_subject("《静夜思》表达了诗人怎样的情感？请赏析意象。")
        assert subject == "语文"
        assert score >= 2

    def test_english_grammar_question(self):
        subject, score = detect_subject(
            "What is the difference between past tense and present perfect tense?"
        )
        assert subject == "英语"
        assert score >= 2

    def test_ambiguous_greeting_no_subject(self):
        subject, _ = detect_subject("你好，张宇老师")
        assert subject is None


class TestSubjectMismatch:
    def test_math_tab_with_english_question(self):
        mm = check_subject_mismatch(
            "请翻译：I love reading books every day.",
            "数学",
        )
        assert mm is not None
        assert mm.detected == "英语"
        assert mm.selected == "数学"

    def test_chinese_tab_with_equation(self):
        mm = check_subject_mismatch(
            "解方程 2x + 5 = 15，求 x 的值",
            "语文",
        )
        assert mm is not None
        assert mm.detected == "数学"

    def test_matching_subject_no_mismatch(self):
        mm = check_subject_mismatch("勾股定理怎么用？直角三角形已知两边求第三边", "数学")
        assert mm is None

    def test_mismatch_reply_mentions_switch(self):
        mm = check_subject_mismatch("请帮我分析这篇文言文的实词", "英语")
        assert mm is not None
        reply = mismatch_reply(mm)
        assert mm.detected in reply
        assert "切换" in reply
