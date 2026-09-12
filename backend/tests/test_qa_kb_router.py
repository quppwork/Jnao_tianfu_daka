"""学科答疑 — 知识库路径路由（学法/练法 vs 旧教学法 vs 不查库）"""

from app.services.qa_kb_router import QaKbPath, resolve_qa_kb_path
from app.services.qa_rag_router import should_use_rag


class TestResolveQaKbPath:
    def test_how_to_study_uses_method_kb(self):
        assert resolve_qa_kb_path("数学怎么学", subject="数学") is QaKbPath.METHOD

    def test_learning_method_uses_method_kb(self):
        assert resolve_qa_kb_path("高中数学有什么学习方法", subject="数学") is QaKbPath.METHOD

    def test_platform_practice_skill_uses_method_kb(self):
        assert resolve_qa_kb_path("开口窍怎么练才有效") is QaKbPath.METHOD

    def test_teaching_pedagogy_uses_legacy(self):
        assert (
            resolve_qa_kb_path("四年级分数加法怎么引导孩子列式？", subject="数学")
            is QaKbPath.LEGACY_TEACHING
        )

    def test_homework_image_skips(self):
        assert resolve_qa_kb_path("帮我看这道题", has_image=True) is QaKbPath.NONE

    def test_pure_homework_skips(self):
        assert resolve_qa_kb_path("这道应用题怎么解", subject="数学") is QaKbPath.NONE

    def test_casual_skips(self):
        assert resolve_qa_kb_path("再举个例子") is QaKbPath.NONE

    def test_force_on_prefers_method(self):
        assert resolve_qa_kb_path("随便问问", use_rag=True) is QaKbPath.METHOD

    def test_force_off(self):
        assert resolve_qa_kb_path("数学怎么学", use_rag=False) is QaKbPath.NONE


class TestShouldUseRagCompat:
    """旧 should_use_rag 需覆盖学法问句，便于 runner / 回归 fixture 一致。"""

    def test_how_to_study_triggers(self):
        assert should_use_rag("数学怎么学", subject="数学") is True

    def test_practice_skill_triggers(self):
        assert should_use_rag("超脑阅读怎么练") is True
