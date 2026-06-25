"""学科答疑 RAG 路由规则"""

from app.services.qa_rag_router import should_use_rag


class TestRagRouter:
    def test_teaching_question_uses_rag(self):
        assert should_use_rag("四年级分数加法怎么引导孩子列式？", subject="数学") is True

    def test_homework_image_skips_rag(self):
        assert should_use_rag("帮我看这道题", has_image=True) is False

    def test_force_flag(self):
        assert should_use_rag("你好", use_rag=True) is True

    def test_force_off(self):
        assert should_use_rag("课标要求是什么", use_rag=False) is False

    def test_casual_chat_skips_rag(self):
        assert should_use_rag("再举个例子") is False
