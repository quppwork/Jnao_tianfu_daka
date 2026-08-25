"""引导页 RAG 路由 — 触发条件"""

from app.services.guide_rag_router import should_guide_use_rag


def test_talent_query_triggers_rag():
    assert should_guide_use_rag("学者天赋是什么")
    assert should_guide_use_rag("超脑阅读怎么练")
    assert should_guide_use_rag("翻箱进化是什么")


def test_homework_skips_rag():
    assert not should_guide_use_rag("这道题怎么解")
    assert not should_guide_use_rag("帮我做这道应用题")


def test_greeting_skips_rag():
    assert not should_guide_use_rag("你好")
    assert not should_guide_use_rag("谢谢")


def test_force_flags():
    assert should_guide_use_rag("随便", use_rag=True)
    assert not should_guide_use_rag("学者天赋", use_rag=False)
