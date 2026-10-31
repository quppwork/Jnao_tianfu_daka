"""get_report_content：从 assessment.report_json 读摘要。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.harness.tools import get_report_content as tool


@pytest.mark.asyncio
async def test_get_report_content_ok():
    row = SimpleNamespace(
        id=7,
        talent_primary="学者",
        report_json={"talent": "学者", "check_talent": "学者"},
    )
    db = MagicMock()
    db.get.return_value = row
    ctx = SimpleNamespace(db=db, extra={"assessment_id": 7})
    with patch("app.harness.context.current_context", return_value=ctx):
        out = await tool.get_report_content({})
    assert out["ok"] is True
    assert "学者" in out["content"]
    assert out["assessment_id"] == 7


@pytest.mark.asyncio
async def test_get_report_content_missing_id():
    ctx = SimpleNamespace(db=MagicMock(), extra={})
    with patch("app.harness.context.current_context", return_value=ctx):
        out = await tool.get_report_content({})
    assert out["ok"] is False
    assert out["error_kind"] == "input"
