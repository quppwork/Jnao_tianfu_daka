"""拍题解答：模拟模式 / 领域路由 / 题库优先 / 符号校验。"""

from __future__ import annotations

import io

import pytest
from PIL import Image


def _tiny_jpeg() -> bytes:
    img = Image.new("RGB", (64, 48), color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_classify_domain_science():
    from app.agents.solve.domain import classify_domain, profile_for_domain

    assert classify_domain("解方程：x+1=2") == "science"
    assert profile_for_domain("language") == "solve_language"
    assert classify_domain("请翻译下面的 English sentence") == "language"


def test_compress_image_bytes():
    from app.agents.solve.compress import compress_image_bytes

    jpeg, data_url = compress_image_bytes(_tiny_jpeg(), max_side=1600, quality=85)
    assert jpeg[:2] == b"\xff\xd8"
    assert data_url.startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_symbolic_verify_and_bank_tools():
    from app.harness.registry import reset_registry_for_tests
    from app.harness.runtime import call_tool

    reset_registry_for_tests()
    ok = await call_tool(
        "symbolic_verify",
        {"expression": "1+1", "claimed_result": "2"},
        profile="solve_science",
    )
    assert ok.ok
    assert ok.data.get("verified") is True

    bad = await call_tool(
        "symbolic_verify",
        {"expression": "1+1", "claimed_result": "3"},
        profile="solve_science",
    )
    assert bad.ok
    assert bad.data.get("verified") is False

    bank = await call_tool(
        "search_question_bank",
        {"query": "计算 1+1 等于多少"},
        profile="solve_science",
    )
    assert bank.ok and bank.data.get("hit") is True
    assert "2" in str(bank.data.get("answer"))


@pytest.mark.asyncio
async def test_run_solve_photo_mock_bank_hit(monkeypatch):
    """无 API Key 时 OCR 模拟含 1+1 → 题库命中走引导（不直接泄答案）。"""
    from app.harness.registry import reset_registry_for_tests
    from app.agents.solve.runner import run_solve_photo

    reset_registry_for_tests()
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("XKW_API_KEY", raising=False)
    monkeypatch.setattr("app.services.doubao_client.is_configured", lambda: False)
    # 跳过学业规划闸（本用例只验题库引导）
    result = await run_solve_photo(_tiny_jpeg(), user_id=None)
    assert result.get("ok") is True
    assert result.get("source") == "question_bank_guided"
    assert result.get("profile") == "solve_science"
    assert result.get("bank_answer_withheld") is True
    assert "条件" in str(result.get("answer"))


@pytest.mark.asyncio
async def test_run_solve_photo_mock_demo_miss(monkeypatch):
    """题库未命中且无模型 → mock_demo。"""
    from app.harness.registry import reset_registry_for_tests
    from app.agents.solve.runner import run_solve_photo
    from app.harness.types import ToolResult

    reset_registry_for_tests()
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("XKW_API_KEY", raising=False)
    monkeypatch.setattr("app.services.doubao_client.is_configured", lambda: False)

    async def fake_call(name, args=None, *, profile=None, ctx=None):
        del args, profile, ctx
        if name == "ocr_extract":
            return ToolResult(
                ok=True,
                name=name,
                data={
                    "ok": True,
                    "text": "请简述文艺复兴的影响（无题库关键词）",
                    "provider": "mock",
                    "mock": True,
                },
            )
        if name == "search_question_bank":
            return ToolResult(
                ok=True,
                name=name,
                data={"ok": True, "hit": False, "provider": "demo_bank", "mock": True},
            )
        return ToolResult(ok=False, name=name or "", error=f"unexpected tool {name}")

    monkeypatch.setattr("app.harness.runtime.call_tool", fake_call)

    result = await run_solve_photo(_tiny_jpeg(), user_id=None, subject_hint="历史")
    assert result.get("ok") is True
    assert result.get("source") == "mock_demo"
    assert result.get("profile") == "solve_humanities"
    assert result.get("mock") is True


def test_solve_profiles_in_llm():
    from app.harness.llm import PROFILES

    for name in (
        "solve_science",
        "solve_language",
        "solve_humanities",
        "solve_invention",
        "solve_arts",
    ):
        assert name in PROFILES
        assert "tools" in PROFILES[name]


def test_solve_photo_api_sync(client, registered_user):
    uid = registered_user["child_user_id"]
    res = client.post(
        f"/api/solve/photo/sync?user_id={uid}",
        files={"image": ("t.jpg", io.BytesIO(_tiny_jpeg()), "image/jpeg")},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    # 新用户无学业规划 → 闸门拦截；有规划时走引导/题库/LLM
    assert data.get("source") in (
        "need_academic_plan",
        "question_bank_guided",
        "question_bank",
        "mock_demo",
        "llm_rag",
    )
    if data.get("source") == "need_academic_plan":
        assert data.get("ok") is False
        assert data.get("ocr_text")
    else:
        assert data.get("ok") is True
        assert data.get("profile", "").startswith("solve_")


def test_solve_tools_registered():
    from app.harness.registry import reset_registry_for_tests, get_tool

    reset_registry_for_tests()
    assert get_tool("ocr_extract") is not None
    assert get_tool("search_question_bank") is not None
    assert get_tool("symbolic_verify") is not None
