"""三业务提问池：报告 20 / 孩子 30 / 家长 30，互不混用、可轮换。"""

from __future__ import annotations

from app.suggest_prompts.pools import pool_for
from app.suggest_prompts.pools.guide_child import GUIDE_CHILD_POOL
from app.suggest_prompts.pools.guide_parent import GUIDE_PARENT_POOL
from app.suggest_prompts.pools.report_talent import REPORT_TALENT_POOL
from app.suggest_prompts.service import (
    pick_suggest_prompts,
    report_suggest_chips,
    suggest_prompts_payload,
)


def test_pool_sizes_isolated():
    assert len(REPORT_TALENT_POOL) == 20
    assert len(GUIDE_CHILD_POOL) == 30
    assert len(GUIDE_PARENT_POOL) == 30
    assert pool_for("report") is REPORT_TALENT_POOL
    assert pool_for("student") is GUIDE_CHILD_POOL
    assert pool_for("parent") is GUIDE_PARENT_POOL


def test_report_and_guide_texts_do_not_share_same_pool_object():
    report_texts = {c.text for c in REPORT_TALENT_POOL}
    child_texts = {c.text for c in GUIDE_CHILD_POOL}
    parent_texts = {c.text for c in GUIDE_PARENT_POOL}
    # 允许少量常识重叠，但池对象与规模必须隔离
    assert report_texts != child_texts
    assert child_texts != parent_texts
    assert "这份报告怎么看" in report_texts
    assert "家长课堂是什么，有哪些课" in parent_texts
    assert "超脑阅读怎么练" in child_texts


def test_report_chips_format_and_talent():
    items = report_suggest_chips("思者", limit=4, user_id=1, visit_key="r1")
    assert len(items) == 4
    assert all("q" in i for i in items)
    joined = " ".join(i["q"] for i in items)
    assert "{talent}" not in joined


def test_guide_rotate_by_visit():
    a = pick_suggest_prompts("student", limit=3, user_id=9, visit_key="v1")
    b = pick_suggest_prompts("student", limit=3, user_id=9, visit_key="v2")
    assert len(a) == 3 and len(b) == 3
    assert [x["text"] for x in a] != [x["text"] for x in b]
    assert all("label" in i and "text" in i for i in a)


def test_parent_payload_pool_size():
    data = suggest_prompts_payload("parent", limit=3, user_id=2, visit_key="t")
    assert data["audience"] == "parent"
    assert data["pool_size"] == 30
    assert len(data["items"]) == 3


def test_compat_guide_suggest_module():
    from app.services.guide_suggest_prompts import (
        _KB_DOC_PROMPTS,
        _pool_for,
        pick_suggest_prompts as legacy_pick,
    )

    assert len(_KB_DOC_PROMPTS) == 30
    assert len(_pool_for("parent")) == 30
    assert len(legacy_pick("parent", limit=3, visit_key="x")) == 3
