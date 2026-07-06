# -*- coding: utf-8 -*-
"""个性化方案替换 API — POST /api/training/plan/customize"""

import json

import pytest


def _auth(uid: int) -> dict:
    return {"headers": {"X-Child-User-Id": str(uid)}}


def _item_skill(item: dict) -> str | None:
    raw = item.get("instructions") or ""
    try:
        return json.loads(raw).get("skill")
    except (json.JSONDecodeError, TypeError):
        return None


def _mutable_skills(plan: dict) -> list[str]:
    skills = []
    for item in plan.get("items") or []:
        if item.get("checkin_status") == "done":
            continue
        raw = item.get("instructions") or ""
        try:
            inst = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            inst = {}
        if inst.get("item_type") == "elective":
            continue
        if inst.get("blocks_next") is False:
            continue
        sk = inst.get("skill")
        if sk:
            skills.append(sk)
    return skills


class TestPlanCustomizeApi:
    """整体替换今日必修项（不改等级进度）"""

    def test_customize_swaps_skills(self, client, user_ready_for_training):
        uid = user_ready_for_training
        sched = client.post(
            "/api/training/schedule",
            json={"planned_minutes": 40},
            **_auth(uid),
        )
        assert sched.status_code == 200
        plan = sched.json()
        original = _mutable_skills(plan)
        assert len(original) >= 2

        swapped = list(reversed(original))
        res = client.post(
            "/api/training/plan/customize",
            json={"plan_id": plan["plan_id"], "skills": swapped},
            **_auth(uid),
        )
        assert res.status_code == 200, res.text
        updated = _mutable_skills(res.json())
        assert updated == swapped

    def test_customize_rejects_wrong_count(self, client, user_ready_for_training):
        uid = user_ready_for_training
        sched = client.post(
            "/api/training/schedule",
            json={"planned_minutes": 40},
            **_auth(uid),
        )
        plan = sched.json()
        need = len(_mutable_skills(plan))
        res = client.post(
            "/api/training/plan/customize",
            json={"plan_id": plan["plan_id"], "skills": ["超脑阅读"]},
            **_auth(uid),
        )
        assert res.status_code == 400
        assert str(need) in res.json().get("detail", "")

    def test_customize_rejects_unknown_skill(self, client, user_ready_for_training):
        uid = user_ready_for_training
        sched = client.post(
            "/api/training/schedule",
            json={"planned_minutes": 40},
            **_auth(uid),
        )
        plan = sched.json()
        skills = _mutable_skills(plan)
        bad = skills[:-1] + ["不存在技能"]
        res = client.post(
            "/api/training/plan/customize",
            json={"plan_id": plan["plan_id"], "skills": bad},
            **_auth(uid),
        )
        assert res.status_code == 400
        assert "未知技能" in res.json().get("detail", "")

    def test_customize_after_partial_checkin_only_pending(self, client, user_ready_for_training):
        uid = user_ready_for_training
        sched = client.post(
            "/api/training/schedule",
            json={"planned_minutes": 40},
            **_auth(uid),
        )
        plan = sched.json()
        items = plan["items"]
        first = items[0]
        client.post(
            "/api/training/checkin",
            json={
                "plan_id": plan["plan_id"],
                "item_id": first["id"],
                "cards": [{"name": _item_skill(first) or "超脑阅读", "time": "2.5", "wordCount": "900"}],
            },
            **_auth(uid),
        )
        today = client.get("/api/training/today", **_auth(uid)).json()
        pending = _mutable_skills(today)
        assert len(pending) == 1

        replacement = ["影像追忆"] if pending[0] != "影像追忆" else ["超脑阅读"]
        res = client.post(
            "/api/training/plan/customize",
            json={"plan_id": plan["plan_id"], "skills": replacement},
            **_auth(uid),
        )
        assert res.status_code == 200
        assert _mutable_skills(res.json()) == replacement

    def test_customize_preserves_overall_tier(self, client, user_ready_for_training):
        uid = user_ready_for_training
        sched = client.post(
            "/api/training/schedule",
            json={"planned_minutes": 40},
            **_auth(uid),
        )
        plan = sched.json()
        before_tier = plan.get("overall_tier")
        skills = _mutable_skills(plan)
        res = client.post(
            "/api/training/plan/customize",
            json={"plan_id": plan["plan_id"], "skills": list(reversed(skills))},
            **_auth(uid),
        )
        assert res.status_code == 200
        assert res.json().get("overall_tier") == before_tier
