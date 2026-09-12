"""guide_suggest_prompts unit tests"""

from app.services.guide_suggest_prompts import (
    _KB_DOC_PROMPTS,
    _pool_for,
    pick_suggest_prompts,
    suggest_prompts_payload,
)


def test_kb_doc_prompts_pool_size():
    assert len(_KB_DOC_PROMPTS) >= 12
    pool = _pool_for("student")
    assert len(pool) >= 12
    assert len(_pool_for("parent")) >= 12


def test_prompts_rotate_by_visit():
    a = pick_suggest_prompts("parent", limit=3, user_id=9, visit_key="v1")
    b = pick_suggest_prompts("parent", limit=3, user_id=9, visit_key="v2")
    assert len(a) == 3 and len(b) == 3
    assert [x["text"] for x in a] != [x["text"] for x in b]


def test_payload_shape():
    data = suggest_prompts_payload("qa", limit=3, user_id=2, visit_key="t")
    assert data["audience"] == "qa"
    assert len(data["items"]) == 3
    assert all("label" in i and "text" in i for i in data["items"])
