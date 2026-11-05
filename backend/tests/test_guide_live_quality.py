# -*- coding: utf-8 -*-
"""Guide 真豆包话术抽检（默认跳过）。

运行：
  $env:DOUBAO_LIVE_TEST="1"
  .\\.venv\\Scripts\\python.exe -m pytest backend\\tests\\test_guide_live_quality.py -v -s

软断言：关键词命中 ≥1；situation/next_action 硬断言；工具探针检查 tools_used。
"""

from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm.attributes import flag_modified

from app.agents.guide.runner import run_chat
from app.agents.guide.situations import apply_situation
from app.agents.guide.context import build_guide_context
from app.db.models import TrainingItem, TrainingPlan, TrainingRecord
from app.services.assessment_service import save_assessment
from app.services.auth_service import register_child
from app.services.child_training_state import get_training_progress, save_training_progress
from app.services.dev_clock import resolve_training_now
from app.services.training_day import get_training_day

_FIXTURE = Path(__file__).parent / "fixtures" / "guide_live_quality.json"

pytestmark_live = pytest.mark.skipif(
    os.getenv("DOUBAO_LIVE_TEST") != "1",
    reason="设置 DOUBAO_LIVE_TEST=1 才跑真实豆包话术抽检",
)


def _load_fixture() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def soft_keyword_hit(text: str, keywords: list[str]) -> list[str]:
    t = text or ""
    return [kw for kw in keywords if kw in t]


def _ensure_assessment(db, user, *, phone_tag: str):
    save_assessment(
        db,
        child_user_id=user.id,
        jnao_record_id=f"live-{phone_tag}-{user.id}",
        answer_bitstring="1" * 35,
        test_type=1,
        report={"talent": "学者", "create_time": "2026-06-18"},
    )
    db.refresh(user)


_PHONE_SEQ = 8800000


def _next_phone() -> str:
    global _PHONE_SEQ
    _PHONE_SEQ += 1
    return f"139{_PHONE_SEQ:08d}"


def seed_situation(db, seed: str, *, phone_suffix: str = ""):
    """按 seed 造库，返回 (user_id, expected_situation)."""
    _ = phone_suffix
    user = register_child(db, parent_phone=_next_phone(), nickname=f"抽检{seed[:6]}")
    day = get_training_day(resolve_training_now(db, user.id))

    if seed == "need_assessment":
        return user.id, "need_assessment"

    _ensure_assessment(db, user, phone_tag=str(user.id))

    if seed == "ready_to_train":
        db.add(
            TrainingRecord(
                child_user_id=user.id,
                train_date=day - timedelta(days=1),
                ability_type="影像追忆",
            )
        )
        db.commit()
        return user.id, "ready_to_train"

    if seed == "sparse_return":
        db.add(
            TrainingRecord(
                child_user_id=user.id,
                train_date=day - timedelta(days=5),
                ability_type="扫描速记",
            )
        )
        db.commit()
        return user.id, "sparse_return"

    if seed == "training_in_progress":
        plan = TrainingPlan(
            child_user_id=user.id,
            plan_date=day,
            planned_minutes=40,
            status="pending",
        )
        db.add(plan)
        db.flush()
        item = TrainingItem(
            plan_id=plan.id,
            sort_order=1,
            title="进行中项",
            ability_type="影像追忆",
            checkin_status="pending",
            watch_progress={"pct": 30},
        )
        db.add(item)
        db.commit()
        return user.id, "training_in_progress"

    if seed == "training_done":
        plan = TrainingPlan(
            child_user_id=user.id,
            plan_date=day,
            planned_minutes=40,
            status="completed",
        )
        db.add(plan)
        db.flush()
        db.add(
            TrainingItem(
                plan_id=plan.id,
                sort_order=1,
                title="已完成项",
                ability_type="影像追忆",
                checkin_status="done",
            )
        )
        db.add(
            TrainingRecord(
                child_user_id=user.id,
                plan_id=plan.id,
                train_date=day,
                ability_type="影像追忆",
            )
        )
        state = get_training_progress(user)
        state["training_days"] = max(1, int(state.get("training_days") or 0))
        save_training_progress(db, user, state)
        flag_modified(user, "profile_json")
        db.commit()
        return user.id, "training_done"

    raise ValueError(f"unknown seed: {seed}")


def test_live_quality_fixture_shape():
    data = _load_fixture()
    assert len(data["chat_cases"]) == 5
    assert len(data["tool_cases"]) >= 1
    for c in data["chat_cases"]:
        assert c["seed"] and c["message"] and c["expect_keywords_any"]


def test_soft_keyword_helper():
    hits = soft_keyword_hit("今天可以去今日训练打卡", ["训练", "天赋", "答疑"])
    assert hits == ["训练"]


def test_seed_situations_match_resolver(db_session):
    for seed, expect in [
        ("need_assessment", "need_assessment"),
        ("ready_to_train", "ready_to_train"),
        ("sparse_return", "sparse_return"),
        ("training_in_progress", "training_in_progress"),
        ("training_done", "training_done"),
    ]:
        uid, _ = seed_situation(db_session, seed, phone_suffix=seed)
        ctx = apply_situation(build_guide_context(db_session, uid))
        assert ctx.situation == expect, f"{seed}: got {ctx.situation}"


@pytestmark_live
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    _load_fixture()["chat_cases"],
    ids=lambda c: c["id"],
)
async def test_live_chat_tendency(db_session, case):
    from app.services.doubao_client import is_configured

    if not is_configured():
        pytest.skip("豆包 API Key 未配置")

    uid, _ = seed_situation(db_session, case["seed"], phone_suffix=case["id"][:8])
    result = await run_chat(db_session, uid, case["message"], history=[], use_tools=True)
    reply = result.get("reply") or ""
    print(f"\n[{case['id']}] situation={result.get('situation')} next={result.get('next_action')}")
    print(f"Q: {case['message']}")
    print(f"A: {reply}")
    print(f"tools: {result.get('tools_used')}")

    assert result.get("situation") == case["expect_situation"]
    assert result.get("next_action") == case["expect_next_action"]
    hits = soft_keyword_hit(reply, case["expect_keywords_any"])
    assert hits, (
        f"话术未命中期望关键词 {case['expect_keywords_any']}；回复={reply!r}"
    )


@pytestmark_live
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    _load_fixture()["tool_cases"],
    ids=lambda c: c["id"],
)
async def test_live_tool_probe(db_session, case):
    from app.services.doubao_client import is_configured

    if not is_configured():
        pytest.skip("豆包 API Key 未配置")

    uid, _ = seed_situation(db_session, case["seed"], phone_suffix=case["id"][:8])
    result = await run_chat(db_session, uid, case["message"], history=[], use_tools=True)
    used = [t.get("name") for t in (result.get("tools_used") or [])]
    print(f"\n[{case['id']}] tools={used} reply={(result.get('reply') or '')[:120]}")
    expect = set(case["expect_tools_any"])
    assert expect.intersection(used), (
        f"期望调用工具之一 {sorted(expect)}，实际={used}"
    )
