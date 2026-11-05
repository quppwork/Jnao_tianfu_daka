"""引导编排路径纯函数测试。"""

from app.agents.guide.pipeline import GuidePath, resolve_guide_path


def test_resolve_qa_handoff():
    assert resolve_guide_path("我有一道数学题不会做", kb_agent_ready=True) is GuidePath.QA_HANDOFF


def test_resolve_kb_agent():
    assert resolve_guide_path("火箭提分营是什么", kb_agent_ready=True) is GuidePath.KB_AGENT


def test_resolve_legacy_when_kb_off():
    assert resolve_guide_path("超脑阅读怎么练", kb_agent_ready=False) is GuidePath.LEGACY_RAG


def test_memory_fold_policy():
    from app.agents.memory_policy import fold_overflow_history, MAX_DIGEST_CHARS

    msgs = [{"role": "user", "content": f"m{i}"} for i in range(20)]
    recent, mem = fold_overflow_history(msgs, {"rolling_summary": ""}, keep=4)
    assert len(recent) == 4
    assert mem["rolling_summary"]
    assert len(mem["rolling_summary"]) <= MAX_DIGEST_CHARS
