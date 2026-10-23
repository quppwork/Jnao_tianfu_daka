"""今日修炼端到端：排课 → 看视频 → 听音频 → 打卡判定 → 多日升段。

全部走真实 HTTP + DB + mastery 判定，不捏造中间结果。
覆盖：低年级 / 高年级、连续三次达标、中途失败清零、全日清单跑完。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import ChildUser, TrainingItem
from app.services.child_training_state import get_training_progress
from app.services.dev_clock import set_time_override
from app.services.training_day import TZ


def _auth(uid: int) -> dict:
    return {"headers": {"X-Child-User-Id": str(uid)}}


def _parse_skill(item: dict) -> str:
    raw = item.get("instructions")
    if isinstance(raw, dict):
        return str(raw.get("skill") or "")
    if isinstance(raw, str) and raw.strip().startswith("{"):
        try:
            return str(json.loads(raw).get("skill") or "")
        except json.JSONDecodeError:
            return ""
    return ""


def _ensure_media(db, item_id: int, *, with_video: bool = True) -> None:
    row = db.get(TrainingItem, item_id)
    assert row is not None
    row.audio_url = "https://example.com/train.mp3"
    if with_video:
        row.video_url = "https://example.com/train.mp4"
    else:
        row.video_url = None
    db.commit()


def _watch_full(client, uid: int, item_id: int, *, has_video: bool) -> None:
    """模拟：先看视频，再听音频（线下训练前媒体必须达标）。"""
    auth = _auth(uid)
    if has_video:
        r = client.post(
            f"/api/training/items/{item_id}/watch-progress",
            json={"watched_sec": 120, "duration_sec": 100, "media": "video"},
            **auth,
        )
        assert r.status_code == 200, r.text
    r = client.post(
        f"/api/training/items/{item_id}/watch-progress",
        json={"watched_sec": 120, "duration_sec": 100, "media": "audio"},
        **auth,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("pct", 0) >= 90 or body.get("video_complete") is True


_PRIMARY_LOW = ("一年级", "二年级", "三年级")
_PRIMARY_HIGH = ("四年级", "五年级", "六年级")
_JUNIOR = ("初一", "初二", "初三")
_SENIOR = ("高一", "高二", "高三")


def _pass_card_for(skill: str, *, grade: str, tier: int = 1) -> dict:
    """按现网阈值生成「应达标」卡片（与 training_tier_thresholds 对齐）。"""
    if skill == "超脑阅读":
        if tier >= 2:
            if grade in _SENIOR:
                return {"name": skill, "time": "5", "wordCount": "5000"}
            if grade in _JUNIOR:
                return {"name": skill, "time": "5", "wordCount": "4000"}
            if grade in _PRIMARY_HIGH:
                return {"name": skill, "time": "5", "wordCount": "2500"}
            return {"name": skill, "time": "5", "wordCount": "2000"}
        if grade in _SENIOR:
            return {"name": skill, "time": "3", "wordCount": "2000"}
        if grade in _JUNIOR:
            return {"name": skill, "time": "3", "wordCount": "1800"}
        if grade in _PRIMARY_HIGH:
            return {"name": skill, "time": "3", "wordCount": "1000"}
        return {"name": skill, "time": "3", "wordCount": "800"}
    if skill == "影像追忆":
        # 与 training_tier_thresholds.yaml 对齐；升段后用新阈值
        if tier >= 5:
            return {"name": skill, "wordCount": "100000", "accuracy": "85", "time": "60"}
        if tier >= 4:
            if grade in _SENIOR:
                return {"name": skill, "wordCount": "10000", "accuracy": "85", "time": "10"}
            if grade in _JUNIOR:
                return {"name": skill, "wordCount": "12000", "accuracy": "85", "time": "10"}
            if grade in _PRIMARY_HIGH:
                return {"name": skill, "wordCount": "8000", "accuracy": "80", "time": "8"}
            return {"name": skill, "wordCount": "6000", "accuracy": "80", "time": "6"}
        if tier >= 3:
            if grade in _SENIOR:
                return {"name": skill, "wordCount": "10000", "accuracy": "85", "time": "10"}
            if grade in _JUNIOR:
                return {"name": skill, "wordCount": "8000", "accuracy": "85", "time": "10"}
            if grade in _PRIMARY_HIGH:
                return {"name": skill, "wordCount": "5000", "accuracy": "80", "time": "8"}
            return {"name": skill, "wordCount": "4000", "accuracy": "80", "time": "6"}
        if tier >= 2:
            if grade in _SENIOR:
                return {"name": skill, "wordCount": "7000", "accuracy": "85", "time": "8"}
            if grade in _JUNIOR:
                return {"name": skill, "wordCount": "6000", "accuracy": "85", "time": "6"}
            if grade in _PRIMARY_HIGH:
                return {"name": skill, "wordCount": "3500", "accuracy": "80", "time": "5"}
            return {"name": skill, "wordCount": "2000", "accuracy": "80", "time": "5"}
        if grade in _SENIOR:
            return {"name": skill, "wordCount": "6000", "accuracy": "80", "time": "6"}
        if grade in _JUNIOR:
            return {"name": skill, "wordCount": "5000", "accuracy": "80", "time": "5"}
        if grade in _PRIMARY_HIGH:
            return {"name": skill, "wordCount": "3000", "accuracy": "75", "time": "4"}
        return {"name": skill, "wordCount": "1500", "accuracy": "75"}
    if skill == "扫描速记":
        # Tier1 阈值 null → 交卡即过；Tier2+ 需倒背
        if tier >= 2:
            wpm = 150 if grade in _PRIMARY_HIGH else 120
            if grade in _SENIOR:
                wpm = 100 if tier == 2 else 200
            return {
                "name": skill,
                "wordCount": str(wpm * 2),
                "time": "2",
                "reverseRecite": True,
            }
        return {"name": skill, "wordCount": "10", "time": "1"}
    if skill == "极速运算":
        return {"name": skill, "completed": True, "correctCount": 10}
    if skill == "极速学习":
        return {"name": skill, "projectName": "火箭提分营", "projectDays": 5}
    return {"name": skill, "wordCount": "100", "time": "1"}


def _fail_card_for(skill: str) -> dict:
    if skill == "超脑阅读":
        return {"name": skill, "time": "10", "wordCount": "50"}
    if skill == "影像追忆":
        return {"name": skill, "wordCount": "100", "accuracy": "10"}
    return {"name": skill, "wordCount": "1", "time": "10", "accuracy": "1"}


def _near_miss_reading(grade: str) -> dict:
    """差一点过：字数略低于该学段 Tier1 阈值。"""
    skill = "超脑阅读"
    if grade in _SENIOR:
        return {"name": skill, "time": "3", "wordCount": "1900"}
    if grade in _JUNIOR:
        return {"name": skill, "time": "3", "wordCount": "1700"}
    if grade in _PRIMARY_HIGH:
        return {"name": skill, "time": "3", "wordCount": "900"}
    return {"name": skill, "time": "3", "wordCount": "700"}


def _strong_pass_reading(grade: str) -> dict:
    """高效学员：明显超阈值（短时高字数）。"""
    skill = "超脑阅读"
    if grade in _SENIOR:
        return {"name": skill, "time": "2", "wordCount": "2200"}
    if grade in _JUNIOR:
        return {"name": skill, "time": "2", "wordCount": "2000"}
    if grade in _PRIMARY_HIGH:
        return {"name": skill, "time": "2", "wordCount": "1200"}
    return {"name": skill, "time": "2", "wordCount": "900"}


def _prep_user(
    client,
    db_session,
    *,
    phone: str,
    nickname: str,
    grade: str,
    cohort: str = "regular",
) -> int:
    reg = client.post(
        "/api/auth/register",
        json={"parent_phone": phone, "nickname": nickname},
    )
    assert reg.status_code == 200, reg.text
    uid = reg.json()["child_user_id"]
    talent = client.post(
        f"/api/talent/report?user_id={uid}",
        json={"answer": "1" * 35, "uid": 888100 + uid, "type": 1},
    )
    assert talent.status_code == 200, talent.text

    child = db_session.get(ChildUser, uid)
    pj = dict(child.profile_json or {})
    pj["grade"] = grade
    pj["training"] = {
        **(pj.get("training") or {}),
        "cohort": cohort,
        "plan_mode": "standard",
    }
    # 老学员权重路径：给足训练日，避免被自动推断成体验固定表
    if cohort == "regular":
        pj["training_progress"] = {
            "skills": {},
            "training_days": 20,
            "training_day_anchor": None,
        }
    child.profile_json = pj
    flag_modified(child, "profile_json")
    db_session.commit()
    return uid


def _set_day(db_session, uid: int, day_index: int, *, base: datetime | None = None) -> datetime:
    base = base or datetime(2026, 9, 1, 10, 0, 0, tzinfo=TZ)
    moment = base + timedelta(days=day_index)
    set_time_override(db_session, uid, moment)
    db_session.commit()
    return moment


def _force_item_skill(db_session, item_id: int, skill: str) -> None:
    row = db_session.get(TrainingItem, item_id)
    payload: dict = {}
    if row.instructions and str(row.instructions).startswith("{"):
        try:
            payload = json.loads(row.instructions)
        except json.JSONDecodeError:
            payload = {}
    payload["skill"] = skill
    payload["item_type"] = "required"
    row.instructions = json.dumps(payload, ensure_ascii=False)
    db_session.commit()


def _run_reading_day(
    client,
    db_session,
    uid: int,
    *,
    day_index: int,
    grade: str,
    card: dict,
    planned_minutes: int = 20,
    expect_pass: bool | None = None,
) -> dict:
    """模拟真实一日：切日 → 排课 → 看视频听音频 → 按卡片打卡判定。"""
    skill = "超脑阅读"
    _set_day(db_session, uid, day_index)
    sched = client.post(
        "/api/training/schedule",
        json={"planned_minutes": planned_minutes},
        **_auth(uid),
    )
    assert sched.status_code == 200, sched.text
    plan = sched.json()
    assert plan.get("items"), f"day={day_index} 排课无 items"
    item = plan["items"][0]
    _force_item_skill(db_session, item["id"], skill)
    body = _complete_one_item(
        client,
        db_session,
        uid,
        plan,
        item,
        card=card,
        expect_pass=expect_pass,
    )
    sr = ((body.get("training_progress") or {}).get("skill_results") or {}).get(skill) or {}
    return {
        "day": day_index,
        "plan": plan,
        "body": body,
        "skill_result": sr,
        "passed": bool(sr.get("passed")),
        "consecutive_pass": int(sr.get("consecutive_pass") or 0),
        "tier_advanced": bool(sr.get("tier_advanced")),
        "tier_after": int(sr.get("tier_after") or 0),
        "planned_minutes": plan.get("planned_minutes"),
    }


def _complete_one_item(
    client,
    db_session,
    uid: int,
    plan: dict,
    item: dict,
    *,
    card: dict,
    expect_pass: bool | None = None,
) -> dict:
    """单关：挂媒体 → 看视频 → 听音频 → 打卡 → 返回 training_progress。"""
    _ensure_media(db_session, item["id"], with_video=True)
    _watch_full(client, uid, item["id"], has_video=True)
    res = client.post(
        "/api/training/checkin",
        json={
            "plan_id": plan["plan_id"],
            "item_id": item["id"],
            "cards": [card],
        },
        **_auth(uid),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    tp = body.get("training_progress") or {}
    skill = card.get("name")
    if expect_pass is not None and skill and tp.get("skill_results"):
        sr = tp["skill_results"].get(skill) or {}
        assert sr.get("passed") is expect_pass, (
            f"skill={skill} expect_pass={expect_pass} got={sr}"
        )
    return body


def _finish_today_all_items(
    client,
    db_session,
    uid: int,
    *,
    planned_minutes: int,
    grade: str,
) -> dict:
    """排课并按顺序跑完今日所有必修关。"""
    sched = client.post(
        "/api/training/schedule",
        json={"planned_minutes": planned_minutes},
        **_auth(uid),
    )
    assert sched.status_code == 200, sched.text
    plan = sched.json()
    assert plan.get("items"), "排课未生成 items"
    last = None
    for item in sorted(plan["items"], key=lambda x: x.get("sort_order") or 0):
        skill = _parse_skill(item) or "超脑阅读"
        # 选修无打卡门槛时也可能出现；仍交卡
        card = _pass_card_for(skill, grade=grade, tier=1)
        last = _complete_one_item(
            client, db_session, uid, plan, item, card=card, expect_pass=True
        )
    today = client.get("/api/training/today", **_auth(uid))
    assert today.status_code == 200, today.text
    today_body = today.json()
    assert today_body.get("status") == "completed" or all(
        i.get("checkin_status") == "done" for i in today_body.get("items") or []
    )
    return {"plan": plan, "last_checkin": last, "today": today_body}


@pytest.fixture
def enable_dev_clock(monkeypatch):
    monkeypatch.setenv("JNAO_DEV_MODE", "1")
    monkeypatch.setenv("JNAO_ENV", "development")


class TestLowGradeDailyJourney:
    """小学低年级：看听打卡 → 连续三日达标升段 → 失败清零。"""

    def test_single_day_full_flow_video_audio_checkin(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        uid = _prep_user(
            client,
            db_session,
            phone="13710001001",
            nickname="低年级全日",
            grade="二年级",
            cohort="regular",
        )
        _set_day(db_session, uid, 0)
        out = _finish_today_all_items(
            client, db_session, uid, planned_minutes=40, grade="二年级"
        )
        plan = out["plan"]
        assert plan["planned_minutes"] == 40
        assert len(plan["items"]) >= 1
        # 实际判定应回写 training_progress
        last = out["last_checkin"]
        assert "training_progress" in last
        assert last["training_progress"].get("skill_results")

        child = db_session.get(ChildUser, uid)
        state = get_training_progress(child)
        # 至少有一项技能连续达标计数被推进
        assert any(
            int((sd or {}).get("consecutive_pass") or 0) >= 1
            for sd in (state.get("skills") or {}).values()
        )

    def test_three_days_consecutive_pass_advances_tier(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        uid = _prep_user(
            client,
            db_session,
            phone="13710001002",
            nickname="低年级连过",
            grade="二年级",
            cohort="regular",
        )
        # 固定 20 分钟 → 权重 1 槽，稳定练超脑，便于断言升段
        skill_name = "超脑阅读"
        for day in range(3):
            _set_day(db_session, uid, day)
            sched = client.post(
                "/api/training/schedule",
                json={"planned_minutes": 20},
                **_auth(uid),
            )
            assert sched.status_code == 200, sched.text
            plan = sched.json()
            item = plan["items"][0]
            # 强制技能标签，避免 OSS/固定表歧义
            row = db_session.get(TrainingItem, item["id"])
            payload = {}
            if row.instructions and str(row.instructions).startswith("{"):
                try:
                    payload = json.loads(row.instructions)
                except json.JSONDecodeError:
                    payload = {}
            payload["skill"] = skill_name
            payload["item_type"] = "required"
            row.instructions = json.dumps(payload, ensure_ascii=False)
            db_session.commit()

            body = _complete_one_item(
                client,
                db_session,
                uid,
                plan,
                item,
                card=_pass_card_for(skill_name, grade="二年级", tier=1),
                expect_pass=True,
            )
            sr = (body.get("training_progress") or {}).get("skill_results") or {}
            result = sr.get(skill_name) or {}
            if day < 2:
                assert result.get("tier_advanced") is False, result
                assert int(result.get("consecutive_pass") or 0) == day + 1
            else:
                assert result.get("tier_advanced") is True, result
                assert int(result.get("tier_after") or 0) == 2
                assert int(result.get("consecutive_pass") or 0) == 0

        child = db_session.get(ChildUser, uid)
        state = get_training_progress(child)
        assert int(state["skills"][skill_name]["tier"]) == 2

    def test_fail_resets_consecutive(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        uid = _prep_user(
            client,
            db_session,
            phone="13710001003",
            nickname="低年级中断",
            grade="二年级",
            cohort="regular",
        )
        skill_name = "超脑阅读"
        # Day0 pass
        _set_day(db_session, uid, 0)
        sched = client.post(
            "/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid)
        )
        plan = sched.json()
        item = plan["items"][0]
        row = db_session.get(TrainingItem, item["id"])
        row.instructions = json.dumps(
            {"skill": skill_name, "item_type": "required"}, ensure_ascii=False
        )
        db_session.commit()
        body1 = _complete_one_item(
            client,
            db_session,
            uid,
            plan,
            item,
            card=_pass_card_for(skill_name, grade="二年级"),
            expect_pass=True,
        )
        assert (
            body1["training_progress"]["skill_results"][skill_name]["consecutive_pass"]
            == 1
        )

        # Day1 fail → 清零
        _set_day(db_session, uid, 1)
        sched2 = client.post(
            "/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid)
        )
        plan2 = sched2.json()
        item2 = plan2["items"][0]
        row2 = db_session.get(TrainingItem, item2["id"])
        row2.instructions = json.dumps(
            {"skill": skill_name, "item_type": "required"}, ensure_ascii=False
        )
        db_session.commit()
        body2 = _complete_one_item(
            client,
            db_session,
            uid,
            plan2,
            item2,
            card=_fail_card_for(skill_name),
            expect_pass=False,
        )
        assert (
            body2["training_progress"]["skill_results"][skill_name]["consecutive_pass"]
            == 0
        )
        assert body2["training_progress"]["skill_results"][skill_name][
            "tier_advanced"
        ] is False


class TestHighGradeDailyJourney:
    """高中：更高阈值；小学达标卡在高中应不通过；全日跑完。"""

    def test_primary_pass_card_fails_on_senior_threshold(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        uid = _prep_user(
            client,
            db_session,
            phone="13710002001",
            nickname="高年级阈值",
            grade="高一",
            cohort="regular",
        )
        _set_day(db_session, uid, 0)
        sched = client.post(
            "/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid)
        )
        assert sched.status_code == 200, sched.text
        plan = sched.json()
        item = plan["items"][0]
        skill = "超脑阅读"
        row = db_session.get(TrainingItem, item["id"])
        row.instructions = json.dumps(
            {"skill": skill, "item_type": "required"}, ensure_ascii=False
        )
        db_session.commit()

        # 小学一阶刚好过的卡：高中一阶应不过（2000字/3分）
        body = _complete_one_item(
            client,
            db_session,
            uid,
            plan,
            item,
            card={"name": skill, "time": "3", "wordCount": "800"},
            expect_pass=False,
        )
        detail = (
            body["training_progress"]["skill_results"][skill]
            .get("threshold_detail") or {}
        ).get("detail", "")
        assert "未达标" in detail or body["training_progress"]["skill_results"][skill][
            "passed"
        ] is False

    def test_senior_pass_and_three_day_advance(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        uid = _prep_user(
            client,
            db_session,
            phone="13710002002",
            nickname="高年级连过",
            grade="高一",
            cohort="regular",
        )
        skill = "超脑阅读"
        for day in range(3):
            _set_day(db_session, uid, day)
            sched = client.post(
                "/api/training/schedule",
                json={"planned_minutes": 20},
                **_auth(uid),
            )
            assert sched.status_code == 200, sched.text
            plan = sched.json()
            item = plan["items"][0]
            row = db_session.get(TrainingItem, item["id"])
            row.instructions = json.dumps(
                {"skill": skill, "item_type": "required"}, ensure_ascii=False
            )
            db_session.commit()
            body = _complete_one_item(
                client,
                db_session,
                uid,
                plan,
                item,
                card=_pass_card_for(skill, grade="高一", tier=1),
                expect_pass=True,
            )
            sr = body["training_progress"]["skill_results"][skill]
            if day == 2:
                assert sr["tier_advanced"] is True
                assert sr["tier_after"] == 2

    def test_senior_full_day_90min(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        uid = _prep_user(
            client,
            db_session,
            phone="13710002003",
            nickname="高年级全日",
            grade="高一",
            cohort="regular",
        )
        _set_day(db_session, uid, 0)
        out = _finish_today_all_items(
            client, db_session, uid, planned_minutes=90, grade="高一"
        )
        assert len(out["plan"]["items"]) >= 2
        assert out["today"]["status"] == "completed" or all(
            i["checkin_status"] == "done" for i in out["today"]["items"]
        )


class TestMediaGateBeforeCheckin:
    """边界：未听完不能打卡；视频不能代替音频。"""

    def test_blocked_without_audio(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        uid = _prep_user(
            client,
            db_session,
            phone="13710003001",
            nickname="媒体门禁",
            grade="二年级",
            cohort="regular",
        )
        _set_day(db_session, uid, 0)
        sched = client.post(
            "/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid)
        )
        plan = sched.json()
        item = plan["items"][0]
        _ensure_media(db_session, item["id"], with_video=True)
        # 只看视频
        client.post(
            f"/api/training/items/{item['id']}/watch-progress",
            json={"watched_sec": 100, "duration_sec": 100, "media": "video"},
            **_auth(uid),
        )
        blocked = client.post(
            "/api/training/checkin",
            json={
                "plan_id": plan["plan_id"],
                "item_id": item["id"],
                "cards": [_pass_card_for("超脑阅读", grade="二年级")],
            },
            **_auth(uid),
        )
        assert blocked.status_code == 403, blocked.text
        assert "听完" in blocked.json().get("detail", "")


class TestRemainingGradeBands:
    """补齐小学高段 / 初中：阈值边界 + 三日升段。"""

    @pytest.mark.parametrize(
        "grade,fail_words,pass_words,phone",
        [
            ("四年级", "900", "1000", "13710004001"),
            ("初一", "1700", "1800", "13710004002"),
        ],
    )
    def test_threshold_boundary_by_band(
        self,
        client,
        db_session,
        mock_jnao,
        enable_dev_clock,
        grade,
        fail_words,
        pass_words,
        phone,
    ):
        uid = _prep_user(
            client,
            db_session,
            phone=phone,
            nickname=f"阈值-{grade}",
            grade=grade,
            cohort="regular",
        )
        skill = "超脑阅读"
        # 先用不达标卡
        _set_day(db_session, uid, 0)
        sched = client.post(
            "/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid)
        )
        assert sched.status_code == 200, sched.text
        plan = sched.json()
        item = plan["items"][0]
        _force_item_skill(db_session, item["id"], skill)
        fail_body = _complete_one_item(
            client,
            db_session,
            uid,
            plan,
            item,
            card={"name": skill, "time": "3", "wordCount": fail_words},
            expect_pass=False,
        )
        assert fail_body["training_progress"]["skill_results"][skill]["passed"] is False

        # 次日达标卡
        out = _run_reading_day(
            client,
            db_session,
            uid,
            day_index=1,
            grade=grade,
            card={"name": skill, "time": "3", "wordCount": pass_words},
            expect_pass=True,
        )
        assert out["passed"] is True
        assert out["consecutive_pass"] == 1

    @pytest.mark.parametrize(
        "grade,phone",
        [("四年级", "13710005001"), ("初一", "13710005002")],
    )
    def test_three_day_advance_for_band(
        self, client, db_session, mock_jnao, enable_dev_clock, grade, phone
    ):
        uid = _prep_user(
            client,
            db_session,
            phone=phone,
            nickname=f"升段-{grade}",
            grade=grade,
            cohort="regular",
        )
        for day in range(3):
            out = _run_reading_day(
                client,
                db_session,
                uid,
                day_index=day,
                grade=grade,
                card=_pass_card_for("超脑阅读", grade=grade, tier=1),
                planned_minutes=20,
                expect_pass=True,
            )
            if day < 2:
                assert out["tier_advanced"] is False
                assert out["consecutive_pass"] == day + 1
            else:
                assert out["tier_advanced"] is True
                assert out["tier_after"] == 2


class TestLearnerPersonasMultiDay:
    """模拟三类学员：低效挣扎、中等起伏、高效短训 — 按天真实走流程。"""

    def test_high_efficiency_short_sessions_advance_in_3_days(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        """高效：每日 20 分钟、明显超阈值，连续 3 天升段。"""
        grade = "四年级"
        uid = _prep_user(
            client,
            db_session,
            phone="13710006001",
            nickname="高效学员",
            grade=grade,
            cohort="regular",
        )
        diary = []
        for day in range(3):
            out = _run_reading_day(
                client,
                db_session,
                uid,
                day_index=day,
                grade=grade,
                card=_strong_pass_reading(grade),
                planned_minutes=20,
                expect_pass=True,
            )
            diary.append(out)
            assert out["planned_minutes"] == 20

        assert [d["passed"] for d in diary] == [True, True, True]
        assert diary[0]["consecutive_pass"] == 1
        assert diary[1]["consecutive_pass"] == 2
        assert diary[2]["tier_advanced"] is True
        assert diary[2]["tier_after"] == 2

        child = db_session.get(ChildUser, uid)
        state = get_training_progress(child)
        assert int(state["skills"]["超脑阅读"]["tier"]) == 2

    def test_medium_efficiency_volatile_then_advance(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        """中等：起起伏伏，需多日才凑满连续 3 次达标。"""
        grade = "初一"
        uid = _prep_user(
            client,
            db_session,
            phone="13710006002",
            nickname="中等起伏",
            grade=grade,
            cohort="regular",
        )
        # 序列：过、挂、过、过、挂、过、过、过 → 第 8 天（index=7）升段
        sequence = [
            ("pass", _pass_card_for("超脑阅读", grade=grade), True, 1, False),
            ("fail", _fail_card_for("超脑阅读"), False, 0, False),
            ("pass", _pass_card_for("超脑阅读", grade=grade), True, 1, False),
            ("pass", _pass_card_for("超脑阅读", grade=grade), True, 2, False),
            ("fail", _near_miss_reading(grade), False, 0, False),
            ("pass", _pass_card_for("超脑阅读", grade=grade), True, 1, False),
            ("pass", _pass_card_for("超脑阅读", grade=grade), True, 2, False),
            ("pass", _pass_card_for("超脑阅读", grade=grade), True, 0, True),
        ]
        diary = []
        for day, (_label, card, expect_pass, expect_cp, expect_adv) in enumerate(sequence):
            out = _run_reading_day(
                client,
                db_session,
                uid,
                day_index=day,
                grade=grade,
                card=card,
                planned_minutes=40,
                expect_pass=expect_pass,
            )
            diary.append(out)
            assert out["passed"] is expect_pass, f"day={day} {_label}"
            assert out["consecutive_pass"] == expect_cp, f"day={day} cp"
            assert out["tier_advanced"] is expect_adv, f"day={day} adv"

        assert diary[-1]["tier_after"] == 2
        assert sum(1 for d in diary if d["passed"]) == 6
        assert sum(1 for d in diary if not d["passed"]) == 2
        # 中等学员比高效多花天数
        assert len(diary) > 3

        child = db_session.get(ChildUser, uid)
        assert int(get_training_progress(child)["skills"]["超脑阅读"]["tier"]) == 2

    def test_low_efficiency_long_struggle_then_advance(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        """低效：时长不短但成绩差，多次失败与差一点，最终才连过升段。"""
        grade = "二年级"
        uid = _prep_user(
            client,
            db_session,
            phone="13710006003",
            nickname="低效挣扎",
            grade=grade,
            cohort="regular",
        )
        # 前 5 天挂 / 差一点；中间又断；最后 3 天连过
        sequence = [
            _fail_card_for("超脑阅读"),
            _near_miss_reading(grade),
            _fail_card_for("超脑阅读"),
            _near_miss_reading(grade),
            _fail_card_for("超脑阅读"),
            _pass_card_for("超脑阅读", grade=grade),  # day5 cp=1
            _fail_card_for("超脑阅读"),  # reset
            _pass_card_for("超脑阅读", grade=grade),  # cp=1
            _pass_card_for("超脑阅读", grade=grade),  # cp=2
            _near_miss_reading(grade),  # reset again
            _pass_card_for("超脑阅读", grade=grade),
            _pass_card_for("超脑阅读", grade=grade),
            _pass_card_for("超脑阅读", grade=grade),  # advance
        ]
        expect_pass = [
            False,
            False,
            False,
            False,
            False,
            True,
            False,
            True,
            True,
            False,
            True,
            True,
            True,
        ]
        expect_cp = [0, 0, 0, 0, 0, 1, 0, 1, 2, 0, 1, 2, 0]
        diary = []
        for day, card in enumerate(sequence):
            out = _run_reading_day(
                client,
                db_session,
                uid,
                day_index=day,
                grade=grade,
                card=card,
                planned_minutes=90,
                expect_pass=expect_pass[day],
            )
            diary.append(out)
            assert out["consecutive_pass"] == expect_cp[day], f"day={day}"
            assert out["planned_minutes"] == 90

        assert diary[-1]["tier_advanced"] is True
        assert diary[-1]["tier_after"] == 2
        # 低效：训练天数明显多于高效的 3 天
        assert len(diary) >= 10
        fail_days = sum(1 for d in diary if not d["passed"])
        assert fail_days >= 5

        child = db_session.get(ChildUser, uid)
        assert int(get_training_progress(child)["skills"]["超脑阅读"]["tier"]) == 2

    def test_high_efficiency_senior_full_day_then_streak(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        """高效高中：先短时全日清单，再连续两日单技能达标凑满升段。"""
        grade = "高一"
        uid = _prep_user(
            client,
            db_session,
            phone="13710006004",
            nickname="高效高中",
            grade=grade,
            cohort="regular",
        )
        # Day0：短时全日（按排课 items 全跑完）
        _set_day(db_session, uid, 0)
        full = _finish_today_all_items(
            client, db_session, uid, planned_minutes=30, grade=grade
        )
        assert full["today"].get("status") == "completed" or all(
            i.get("checkin_status") == "done" for i in full["today"].get("items") or []
        )

        # Day1–2：专练超脑阅读连过（若 day0 已对超脑计过，需从实际 cp 续）
        child = db_session.get(ChildUser, uid)
        cp0 = int(
            get_training_progress(child)["skills"].get("超脑阅读", {}).get(
                "consecutive_pass"
            )
            or 0
        )
        tier0 = int(get_training_progress(child)["skills"]["超脑阅读"]["tier"])

        # 若 day0 全日已让超脑升到 2，则本用例已满足「高效快进」
        if tier0 >= 2:
            return

        need = max(0, 3 - cp0)
        for i in range(need):
            out = _run_reading_day(
                client,
                db_session,
                uid,
                day_index=1 + i,
                grade=grade,
                card=_strong_pass_reading(grade),
                planned_minutes=20,
                expect_pass=True,
            )
            if i == need - 1:
                assert out["tier_advanced"] is True or out["tier_after"] >= 2

        child = db_session.get(ChildUser, uid)
        assert int(get_training_progress(child)["skills"]["超脑阅读"]["tier"]) >= 2
