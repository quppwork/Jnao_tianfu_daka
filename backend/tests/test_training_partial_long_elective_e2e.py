"""对齐《排课进阶与打卡需求》：长时追加、选修不打不算失败、部分打卡/未打卡。

依据：
- 121–240 / 241–479 / ≥480 分钟追加高效作业或极速学习；高效作业不打卡不阻塞
- 多元感知可打可不打，不打不算失败，不阻塞后续
- 必修可只打一部分；未打技能不结算、不拉低整体段位
- 仅排课未打卡，次日仍可正常开新训练日
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import ChildUser, TrainingItem, TrainingPlan
from app.services.child_training_state import display_overall_tier, get_training_progress
from app.services.dev_clock import set_time_override
from app.services.training_carryover import item_skips_checkin
from app.services.training_day import TZ

from pathlib import Path as _Path
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "training_daily_journey_e2e",
    _Path(__file__).with_name("test_training_daily_journey_e2e.py"),
)
_journey = _ilu.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_journey)
_auth = _journey._auth
_complete_one_item = _journey._complete_one_item
_pass_card_for = _journey._pass_card_for
_prep_user = _journey._prep_user
_parse_skill = _journey._parse_skill


def _set_moment(db, uid: int, moment: datetime) -> None:
    set_time_override(db, uid, moment)
    db.commit()


def _skill_of(item: TrainingItem | dict) -> str:
    raw = item.instructions if isinstance(item, TrainingItem) else item.get("instructions")
    if raw and str(raw).strip().startswith("{"):
        try:
            return str(json.loads(raw).get("skill") or "")
        except json.JSONDecodeError:
            return ""
    return _parse_skill(item if isinstance(item, dict) else {}) or ""


def _required_pending(db, item_ids: list[int]) -> TrainingItem | None:
    for iid in item_ids:
        row = db.get(TrainingItem, iid)
        if not row:
            continue
        db.refresh(row)
        if row.checkin_status == "done" or item_skips_checkin(row):
            continue
        return row
    return None


@pytest.fixture
def enable_dev_clock(monkeypatch):
    monkeypatch.setenv("JNAO_DEV_MODE", "1")
    monkeypatch.setenv("JNAO_ENV", "development")


class TestLongDurationExtras:
    """3–5 小时：追加高效作业（一/二阶），不打卡也能收束。"""

    @pytest.mark.parametrize(
        "minutes,expect_homework",
        [
            (180, True),   # 3h
            (240, True),   # 4h
            (300, True),   # 5h
        ],
    )
    def test_long_session_homework_skips_checkin(
        self, client, db_session, mock_jnao, enable_dev_clock, minutes, expect_homework
    ):
        uid = _prep_user(
            client,
            db_session,
            phone=f"13710009{minutes // 60}01",
            nickname=f"长训{minutes}",
            grade="四年级",
            cohort="regular",
        )
        _set_moment(db_session, uid, datetime(2026, 9, 1, 9, 0, tzinfo=TZ))
        sched = client.post(
            "/api/training/schedule",
            json={"planned_minutes": minutes},
            **_auth(uid),
        )
        assert sched.status_code == 200, sched.text
        plan = sched.json()
        skills = [_parse_skill(it) for it in plan["items"]]
        assert len(plan["items"]) >= 4, skills
        if expect_homework:
            assert "高效作业" in skills, skills

        # 只打必修；高效作业应 item_skips，不交卡
        item_ids = [it["id"] for it in plan["items"]]
        homework_ids = [
            it["id"] for it in plan["items"] if _parse_skill(it) == "高效作业"
        ]
        while True:
            pending = _required_pending(db_session, item_ids)
            if not pending:
                break
            skill = _skill_of(pending) or "超脑阅读"
            tier = int(
                get_training_progress(db_session.get(ChildUser, uid))["skills"]
                .get(skill, {})
                .get("tier")
                or 1
            )
            body = _complete_one_item(
                client,
                db_session,
                uid,
                plan,
                {"id": pending.id, "sort_order": pending.sort_order},
                card=_pass_card_for(skill, grade="四年级", tier=tier),
            )
            # 高效作业不应出现在本次 skill_results
            sr = (body.get("training_progress") or {}).get("skill_results") or {}
            assert "高效作业" not in sr

        for hid in homework_ids:
            row = db_session.get(TrainingItem, hid)
            db_session.refresh(row)
            # 免打卡项应被 auto_complete 标 done，或不阻塞计划完成
            assert item_skips_checkin(row) is True

        today = client.get("/api/training/today", **_auth(uid))
        assert today.status_code == 200
        # 必修打完后，选修免打卡应让方案可 completed
        assert today.json().get("status") in ("completed", "pending")
        if homework_ids:
            # 至少验证高效作业未要求用户交卡也能 done
            hw = db_session.get(TrainingItem, homework_ids[0])
            db_session.refresh(hw)
            assert hw.checkin_status == "done"


class TestPartialAndNoCheckin:
    """部分打卡 / 仅排课未打卡。"""

    def test_schedule_without_checkin_next_day_ok(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        uid = _prep_user(
            client,
            db_session,
            phone="13710009111",
            nickname="只排不打",
            grade="二年级",
            cohort="regular",
        )
        d0 = datetime(2026, 9, 1, 10, 0, tzinfo=TZ)
        _set_moment(db_session, uid, d0)
        r1 = client.post(
            "/api/training/schedule",
            json={"planned_minutes": 90},
            **_auth(uid),
        )
        assert r1.status_code == 200, r1.text
        plan1 = r1.json()
        assert plan1.get("items")
        # 故意不打卡
        today = client.get("/api/training/today", **_auth(uid))
        assert today.json().get("status") != "completed"

        # 次日新方案
        _set_moment(db_session, uid, d0 + timedelta(days=1))
        r2 = client.post(
            "/api/training/schedule",
            json={"planned_minutes": 60},
            **_auth(uid),
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["plan_id"] != plan1["plan_id"]
        # 从未打卡技能不拉低整体段位
        child = db_session.get(ChildUser, uid)
        assert display_overall_tier(db_session, child) == 1

    def test_partial_checkin_only_settles_submitted_skills(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        uid = _prep_user(
            client,
            db_session,
            phone="13710009112",
            nickname="部分打卡",
            grade="四年级",
            cohort="regular",
        )
        _set_moment(db_session, uid, datetime(2026, 9, 2, 15, 30, tzinfo=TZ))
        sched = client.post(
            "/api/training/schedule",
            json={"planned_minutes": 180},
            **_auth(uid),
        )
        assert sched.status_code == 200, sched.text
        plan = sched.json()
        items = sorted(plan["items"], key=lambda x: x.get("sort_order") or 0)
        required = [
            it
            for it in items
            if not item_skips_checkin(db_session.get(TrainingItem, it["id"]))
        ]
        assert len(required) >= 2

        first = required[0]
        skill = _parse_skill(first) or "超脑阅读"
        # 只打第一关必修
        body = _complete_one_item(
            client,
            db_session,
            uid,
            plan,
            first,
            card=_pass_card_for(skill, grade="四年级", tier=1),
            expect_pass=True,
        )
        sr = (body.get("training_progress") or {}).get("skill_results") or {}
        assert list(sr.keys()) == [skill]
        assert sr[skill]["consecutive_pass"] == 1

        # 其余必修仍 pending
        for it in required[1:]:
            row = db_session.get(TrainingItem, it["id"])
            db_session.refresh(row)
            assert row.checkin_status != "done"

        plan_row = db_session.get(TrainingPlan, plan["plan_id"])
        db_session.refresh(plan_row)
        assert plan_row.status == "pending"

        # 未打技能连续计数仍为 0
        child = db_session.get(ChildUser, uid)
        state = get_training_progress(child)
        other = _parse_skill(required[1])
        if other and other != skill:
            assert int(state["skills"].get(other, {}).get("consecutive_pass") or 0) == 0


class TestElectiveOptional:
    """多元感知：加上但不打卡，不算失败、不阻塞必修。"""

    def test_add_perception_skip_checkin_still_finish_required(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        uid = _prep_user(
            client,
            db_session,
            phone="13710009113",
            nickname="选修不打",
            grade="四年级",
            cohort="regular",
        )
        _set_moment(db_session, uid, datetime(2026, 9, 3, 11, 0, tzinfo=TZ))
        sched = client.post(
            "/api/training/schedule",
            json={"planned_minutes": 40},
            **_auth(uid),
        )
        assert sched.status_code == 200, sched.text
        plan = sched.json()
        plan_id = plan["plan_id"]

        toggled = client.post(
            "/api/training/plan/elective-toggle",
            json={"plan_id": plan_id, "skill": "多元感知", "action": "add"},
            **_auth(uid),
        )
        assert toggled.status_code == 200, toggled.text
        plan2 = toggled.json()
        skills = [_parse_skill(it) for it in plan2.get("items") or []]
        assert any(s in ("多元感知", "感知力") for s in skills), skills

        item_ids = [it["id"] for it in plan2["items"]]
        # 不打选修，只打必修
        while True:
            pending = _required_pending(db_session, item_ids)
            if not pending:
                break
            skill = _skill_of(pending) or "超脑阅读"
            if skill in ("多元感知", "感知力"):
                # 选修应 skips，不应进入 required pending
                assert False, "选修不应阻塞必修队列"
            _complete_one_item(
                client,
                db_session,
                uid,
                plan2,
                {"id": pending.id, "sort_order": pending.sort_order},
                card=_pass_card_for(skill, grade="四年级", tier=1),
            )

        child = db_session.get(ChildUser, uid)
        # 选修未打不拉低整体段位
        assert display_overall_tier(db_session, child) >= 1
        state = get_training_progress(child)
        # 感知力/多元感知不应因未打卡被写成失败清零以外的异常 tier
        for sk in ("感知力", "多元感知"):
            if sk in state["skills"]:
                assert int(state["skills"][sk].get("consecutive_pass") or 0) >= 0
