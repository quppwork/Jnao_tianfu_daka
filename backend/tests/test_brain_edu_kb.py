"""本地脑科学知识库检索（01/02/03）。"""

from pathlib import Path

import pytest

from app.services import brain_edu_kb as kb


@pytest.fixture(autouse=True)
def _clear_cache():
    kb.clear_kb_cache()
    yield
    kb.clear_kb_cache()


def test_resolve_kb_root_or_skip():
    root = kb.resolve_kb_root()
    if root is None:
        pytest.skip("BRAIN_EDU_KB_PATH / 默认路径未配置")
    assert (root / "02-五者天赋体系.md").exists()


def test_local_retrieve_sizhe():
    if not kb.resolve_kb_root():
        pytest.skip("本地 KB 不可用")
    out = kb.local_retrieve("思者孩子作业拖拉、走神怎么办", prefer_docs=list(kb.FOUNDATION))
    assert out["ok"] is True
    assert out["rag_used"] is True
    assert out["rag_block"]
    assert any("02" in (s or "") or "思" in (out["rag_block"] or "") for s in (out.get("sources") or ["x"]))


def test_persona_system_mentions_foundation():
    from app.harness.llm import profile_system

    text = profile_system("consult", persona="sizhe")
    assert "01" in text or "脑科学" in text
    assert "思者" in text
    assert "retrieve_kb" in text
