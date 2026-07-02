import pytest
"""高效作业等单文件技能与 _find_lesson 匹配"""

from app.services.training_curriculum import _find_lesson
from app.services.talent_content_pool import get_talent_content_pool


class TestSingleFileSkillMatch:
    def test_find_gaoxiao_zuoye_scholar(self, db_session):
        pool = get_talent_content_pool(db_session, 1, skill="高效作业", limit=20)
        found = _find_lesson(pool, "高效作业", 1, 1)
        if not pool:
            pytest.skip("xuekeaomi catalog 未导入")
        assert found is not None
        assert "高效作业" in (found.lesson_title or "")
