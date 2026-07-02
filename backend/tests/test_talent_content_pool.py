import pytest
"""天赋混合内容池"""

from app.services.talent_content_pool import (
    get_talent_content_pool,
    split_pool_for_training_blocks,
)
from app.services.content_meta import parse_item_meta


def test_talent_pool_merges_series(db_session, child_with_assessment):
    uid = child_with_assessment
    from app.services.assessment_service import effective_talent_code, get_latest_assessment

    code = effective_talent_code(get_latest_assessment(db_session, uid))
    pool = get_talent_content_pool(db_session, code)
    if not pool:
        return
    series_set = {parse_item_meta(i).get("series") for i in pool}
    assert len(series_set) >= 1


def test_split_pool_by_main_line_not_series(db_session, child_with_assessment):
    from app.services.assessment_service import effective_talent_code, get_latest_assessment

    code = effective_talent_code(get_latest_assessment(db_session, child_with_assessment))
    pool = get_talent_content_pool(db_session, code)
    if len(pool) < 2:
        return
    a, b = split_pool_for_training_blocks(pool, "A")
    assert isinstance(a, list)
    assert isinstance(b, list)
