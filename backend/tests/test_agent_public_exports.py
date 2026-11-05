"""TDD: 公共导出面稳定 — 后端接口依赖的包入口不可断裂。"""

from __future__ import annotations


def test_runtime_exports():
    from app import runtime

    assert hasattr(runtime, "run_turn")
    assert hasattr(runtime, "run_turn_stream")
    assert hasattr(runtime, "Executor")


def test_architecture_exports():
    from app import architecture

    for name in (
        "LlmProvider",
        "McpClient",
        "GuardPolicy",
        "DurableMemoryStore",
        "RunCheckpointStore",
    ):
        assert hasattr(architecture, name)


def test_memory_exports():
    from app import memory

    for name in (
        "ThreadStore",
        "ThreadRef",
        "get_thread_store",
        "CheckpointStore",
        "get_log_store",
    ):
        assert hasattr(memory, name)


def test_assemble_exports():
    from app import assemble

    assert hasattr(assemble, "get_bundle")
    assert hasattr(assemble, "build_bundle")
    assert hasattr(assemble, "reset_bundle")


def test_harness_package_still_exports_turn_names():
    import app.harness as h

    assert callable(h.run_profile_turn)
    assert callable(h.run_agent)
    assert callable(h.iter_agent)
