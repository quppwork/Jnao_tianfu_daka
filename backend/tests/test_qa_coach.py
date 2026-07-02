import pytest
"""教练元数据 — 错题模式检测"""

from app.services.qa_coach import build_coach_metadata, detect_mistake_pattern


class TestQaCoach:
    def test_sizhe_mistake_pattern(self):
        assert detect_mistake_pattern("思者", "我总是想太多不确定") == "overthink"

    def test_build_metadata(self):
        meta = build_coach_metadata(
            talent_primary="学者",
            report_json=None,
            school_stage="primary_high",
            message="这道题怎么做",
        )
        assert meta["coach_hint"]
        assert meta["school_stage"] == "primary_high"
