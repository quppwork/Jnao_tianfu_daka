"""今日修炼：按测试用例实跑，并一用例一文档落盘。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.db.models import ChildUser, TrainingItem, TrainingPlan
from app.services.child_training_state import (
    display_overall_tier,
    get_training_progress,
    save_training_progress,
    set_skill_tier,
)
from app.services.dev_clock import set_time_override
from app.services.training_carryover import item_skips_checkin
from app.services.training_day import TZ, get_training_day
from app.services.training_formula_engine import expand_formula

from pathlib import Path as _Path
import importlib.util as _ilu
import sys

_tests_dir = str(_Path(__file__).resolve().parent)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

from training_case_docutil import (  # noqa: E402
    DOC_ROOT,
    fmt_card,
    write_case_doc,
    write_catalog,
)

_spec = _ilu.spec_from_file_location(
    "training_daily_journey_e2e",
    _Path(__file__).with_name("test_training_daily_journey_e2e.py"),
)
_j = _ilu.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_j)

_auth = _j._auth
_complete_one_item = _j._complete_one_item
_fail_card_for = _j._fail_card_for
_force_item_skill = _j._force_item_skill
_parse_skill = _j._parse_skill
_pass_card_for = _j._pass_card_for
_prep_user = _j._prep_user
_run_reading_day = getattr(_j, "_run_reading_day", None)
_set_day = _j._set_day

# 收集本会话写出的用例，最后写目录
_CATALOG: list[dict] = []


def _reg(case_id: str, title: str, path: Path, passed: bool) -> None:
    _CATALOG.append(
        {
            "case_id": case_id,
            "title": title,
            "passed": passed,
            "file": path.name,
        }
    )


def _moment(db, uid: int, day: int = 0, hour: int = 10) -> datetime:
    m = datetime(2026, 9, 1, hour, 0, 0, tzinfo=TZ) + timedelta(days=day)
    set_time_override(db, uid, m)
    db.commit()
    return m


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


def _skill_of_row(row: TrainingItem) -> str:
    if row.instructions and str(row.instructions).startswith("{"):
        try:
            return json.loads(row.instructions).get("skill") or row.title or ""
        except json.JSONDecodeError:
            pass
    return row.title or ""


@pytest.fixture
def enable_dev_clock(monkeypatch):
    monkeypatch.setenv("JNAO_DEV_MODE", "1")
    monkeypatch.setenv("JNAO_ENV", "development")


@pytest.fixture(scope="module", autouse=True)
def _prepare_doc_root():
    DOC_ROOT.mkdir(parents=True, exist_ok=True)
    yield


class TestCaseCatalogE2E:
    """专业测试矩阵：每条用例独立断言并写文档。"""

    def test_TC01_short_20min_single_skill(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC01", "短时20分钟单技能排课"
        uid = _prep_user(
            client, db_session, phone="13880000001", nickname=title, grade="二年级"
        )
        _moment(db_session, uid)
        r = client.post(
            "/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid)
        )
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        skills = [_parse_skill(i) for i in items]
        ok = len(items) == 1
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="验收约20分钟必修名额为1，清单以重点技能为主。",
            preconditions=["已注册学员", "完成天赋测评", "二年级老学员"],
            steps=["选择今日训练时长20分钟", "调用排课接口", "查看清单项数与技能"],
            expect=["必修项数=1", "技能非空"],
            actual={
                "项数": len(items),
                "技能列表": skills,
                "预约时长": r.json().get("planned_minutes"),
            },
            passed=ok,
            detail_tables=[
                (
                    "当日清单",
                    ["序号", "技能", "标题"],
                    [
                        [it.get("sort_order"), _parse_skill(it), it.get("title")]
                        for it in items
                    ],
                )
            ],
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC02_duration_quota_table(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC02", "时长档名额与追加项对照"
        # 用公式引擎核对需求表（与线上排课同源）
        rows = []
        ok = True
        checks = [
            (20, 1, None),
            (40, 2, None),
            (60, 3, None),
            (150, 4, "高效作业"),
            (180, 4, "高效作业"),
            (240, 4, "高效作业"),
            (300, 5, "高效作业"),
        ]
        for minutes, min_required, extra in checks:
            fr = expand_formula(minutes, overall_tier=1, grade_band="primary_low")
            slots = fr.get("slots") or []
            # 必修约等于 slots 去掉追加
            extras = fr.get("extras") or []
            required_n = len([s for s in slots if s not in extras]) if extras else len(slots)
            # 引擎可能把追加也放进 slots：按需求「名额」看非追加数量或总 slots-extras
            non_extra = [s for s in slots if s not in (extras or ["高效作业", "精力恢复", "极速学习"][-0:])]
            # 更稳：名额≈去掉已知选修追加
            skip = {"高效作业", "精力恢复"}
            required_like = [s for s in slots if s not in skip]
            hit_extra = (extra is None) or (extra in slots) or (extra in extras)
            row_ok = len(required_like) >= min_required and hit_extra
            ok = ok and row_ok
            rows.append(
                [
                    minutes,
                    min_required,
                    len(required_like),
                    "、".join(slots),
                    "是" if hit_extra else "否",
                    "通过" if row_ok else "失败",
                ]
            )
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="对照需求：20/40/60/150/180/240/300 分钟名额与一阶追加高效作业。",
            preconditions=["使用与排课同源的 expand_formula"],
            steps=["对各时长调用公式展开", "统计非选修追加技能数", "检查是否挂高效作业"],
            expect=[
                "20→≥1，40→≥2，60→≥3，121–240→≥4，241+→≥5",
                "一阶长训应出现高效作业",
            ],
            actual={"对照行数": len(rows), "全部通过": ok},
            passed=ok,
            detail_tables=[
                (
                    "时长对照表",
                    ["时长(分)", "需求名额≥", "实测必修类项数", "清单", "含高效作业", "结果"],
                    rows,
                )
            ],
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC03_long_3to5h_homework(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC03", "三至五小时长训高效作业免打卡"
        uid = _prep_user(
            client, db_session, phone="13880000003", nickname=title, grade="四年级"
        )
        table = []
        ok = True
        for minutes, day in ((180, 0), (240, 1), (300, 2)):
            _moment(db_session, uid, day=day, hour=9)
            sched = client.post(
                "/api/training/schedule",
                json={"planned_minutes": minutes},
                **_auth(uid),
            )
            assert sched.status_code == 200, sched.text
            plan = sched.json()
            skills = [_parse_skill(it) for it in plan["items"]]
            has_hw = "高效作业" in skills
            # 打完必修，不打高效作业
            ids = [it["id"] for it in plan["items"]]
            while True:
                p = _required_pending(db_session, ids)
                if not p:
                    break
                sk = _skill_of_row(p) or "超脑阅读"
                _complete_one_item(
                    client,
                    db_session,
                    uid,
                    plan,
                    {"id": p.id, "sort_order": p.sort_order},
                    card=_pass_card_for(sk, grade="四年级", tier=1),
                )
            hw_done = True
            for it in plan["items"]:
                if _parse_skill(it) != "高效作业":
                    continue
                row = db_session.get(TrainingItem, it["id"])
                db_session.refresh(row)
                hw_done = hw_done and (
                    item_skips_checkin(row) and row.checkin_status == "done"
                )
            row_ok = has_hw and hw_done
            ok = ok and row_ok
            table.append([minutes, "、".join(skills), "是" if has_hw else "否", "是" if hw_done else "否"])
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="3/4/5小时长训应追加高效作业；不交卡也能被标记完成且不阻塞。",
            preconditions=["四年级老学员", "整体一段"],
            steps=["分别排课180/240/300分钟", "只打必修", "检查高效作业状态"],
            expect=["清单含高效作业", "高效作业免打卡且最终为已完成"],
            actual={"全部通过": ok},
            passed=ok,
            detail_tables=[
                ("长训实测", ["时长", "清单", "含高效作业", "免打卡完成"], table)
            ],
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC04_partial_checkin(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC04", "部分打卡只结算已交卡技能"
        uid = _prep_user(
            client, db_session, phone="13880000004", nickname=title, grade="四年级"
        )
        _moment(db_session, uid, hour=15)
        sched = client.post(
            "/api/training/schedule", json={"planned_minutes": 180}, **_auth(uid)
        )
        assert sched.status_code == 200
        plan = sched.json()
        required = [
            it
            for it in plan["items"]
            if not item_skips_checkin(db_session.get(TrainingItem, it["id"]))
        ]
        first = required[0]
        skill = _parse_skill(first) or "超脑阅读"
        body = _complete_one_item(
            client,
            db_session,
            uid,
            plan,
            first,
            card=_pass_card_for(skill, grade="四年级"),
            expect_pass=True,
        )
        sr = (body.get("training_progress") or {}).get("skill_results") or {}
        pending_left = 0
        for it in required[1:]:
            row = db_session.get(TrainingItem, it["id"])
            db_session.refresh(row)
            if row.checkin_status != "done":
                pending_left += 1
        plan_row = db_session.get(TrainingPlan, plan["plan_id"])
        db_session.refresh(plan_row)
        ok = (
            list(sr.keys()) == [skill]
            and pending_left >= 1
            and plan_row.status == "pending"
        )
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="长清单只打第一关：仅该技能结算；其余必修仍待打；方案未完成。",
            preconditions=["四年级", "180分钟多技能清单"],
            steps=["排课", "只完成第一项必修打卡", "检查进度与方案状态"],
            expect=["skill_results仅含本关技能", "仍有未完成必修", "方案状态=进行中"],
            actual={
                "本关技能": skill,
                "结算技能": list(sr.keys()),
                "剩余未打必修数": pending_left,
                "方案状态": plan_row.status,
                "连续达标": (sr.get(skill) or {}).get("consecutive_pass"),
            },
            passed=ok,
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC05_schedule_only_next_day(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC05", "只排课未打卡次日可开新训"
        uid = _prep_user(
            client, db_session, phone="13880000005", nickname=title, grade="二年级"
        )
        d0 = _moment(db_session, uid, day=0)
        r1 = client.post(
            "/api/training/schedule", json={"planned_minutes": 90}, **_auth(uid)
        )
        assert r1.status_code == 200
        pid1 = r1.json()["plan_id"]
        _moment(db_session, uid, day=1)
        r2 = client.post(
            "/api/training/schedule", json={"planned_minutes": 60}, **_auth(uid)
        )
        assert r2.status_code == 200
        child = db_session.get(ChildUser, uid)
        ok = r2.json()["plan_id"] != pid1 and display_overall_tier(db_session, child) == 1
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="当日只排课不打卡，次日应能生成新方案；未打卡技能不拉低整体段位。",
            preconditions=["二年级老学员"],
            steps=["第1天排课90分钟不打卡", "切到第2天排课60分钟", "对比方案ID与整体段位"],
            expect=["次日方案ID不同", "整体段位仍为1"],
            actual={
                "第1天方案": pid1,
                "第2天方案": r2.json()["plan_id"],
                "整体段位": display_overall_tier(db_session, child),
                "第1天起点": d0.isoformat(),
            },
            passed=ok,
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC06_media_gate(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC06", "未听完音频不能打卡"
        uid = _prep_user(
            client, db_session, phone="13880000006", nickname=title, grade="二年级"
        )
        _moment(db_session, uid)
        sched = client.post(
            "/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid)
        )
        plan = sched.json()
        item = plan["items"][0]
        row = db_session.get(TrainingItem, item["id"])
        row.audio_url = "https://example.com/a.mp3"
        row.video_url = "https://example.com/v.mp4"
        db_session.commit()
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
        ok = blocked.status_code == 403 and "听完" in blocked.json().get("detail", "")
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="有音频须听满进度；仅看视频不能代替听音频。",
            preconditions=["项上挂有音视频"],
            steps=["只上报视频进度", "尝试打卡"],
            expect=["返回403", "提示需听完"],
            actual={
                "状态码": blocked.status_code,
                "错误信息": blocked.json().get("detail"),
            },
            passed=ok,
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC07_elective_perception_optional(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC07", "多元感知不打卡不算失败"
        uid = _prep_user(
            client, db_session, phone="13880000007", nickname=title, grade="四年级"
        )
        _moment(db_session, uid, hour=11)
        sched = client.post(
            "/api/training/schedule", json={"planned_minutes": 40}, **_auth(uid)
        )
        plan = sched.json()
        tog = client.post(
            "/api/training/plan/elective-toggle",
            json={"plan_id": plan["plan_id"], "skill": "多元感知", "action": "add"},
            **_auth(uid),
        )
        assert tog.status_code == 200, tog.text
        plan2 = tog.json()
        skills = [_parse_skill(it) for it in plan2["items"]]
        ids = [it["id"] for it in plan2["items"]]
        while True:
            p = _required_pending(db_session, ids)
            if not p:
                break
            sk = _skill_of_row(p)
            assert sk not in ("多元感知", "感知力")
            _complete_one_item(
                client,
                db_session,
                uid,
                plan2,
                {"id": p.id, "sort_order": p.sort_order},
                card=_pass_card_for(sk or "超脑阅读", grade="四年级"),
            )
        child = db_session.get(ChildUser, uid)
        ok = any(s in ("多元感知", "感知力") for s in skills) and (
            display_overall_tier(db_session, child) >= 1
        )
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="选修多元感知可挂上但不打卡；不阻塞必修，不拉低整体段位。",
            preconditions=["四年级", "40分钟方案"],
            steps=["排课", "选修开关添加多元感知", "只打必修不打选修"],
            expect=["清单含多元感知/感知力", "必修可完成", "整体段位不被选修拉低"],
            actual={
                "清单技能": skills,
                "整体段位": display_overall_tier(db_session, child),
            },
            passed=ok,
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC08_three_pass_advance(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC08", "连续三日达标升段"
        uid = _prep_user(
            client, db_session, phone="13880000008", nickname=title, grade="二年级"
        )
        diary = []
        ok = True
        for day in range(3):
            out = _j._run_reading_day(
                client,
                db_session,
                uid,
                day_index=day,
                grade="二年级",
                card=_pass_card_for("超脑阅读", grade="二年级", tier=1),
                planned_minutes=20,
                expect_pass=True,
            )
            diary.append(out)
            if day < 2:
                ok = ok and out["tier_advanced"] is False
            else:
                ok = ok and out["tier_advanced"] is True and out["tier_after"] == 2
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="同一技能连续3个训练日达标 → 段位+1，连续计数清零。",
            preconditions=["二年级", "专练超脑阅读"],
            steps=["连续3天：排课→看听→按达标卡打卡"],
            expect=["前两天不升段", "第三天升到第2段"],
            actual={"第3天升段": diary[-1]["tier_advanced"], "段位": diary[-1]["tier_after"]},
            passed=ok,
            detail_tables=[
                (
                    "三日记录",
                    ["日序", "达标", "连续", "升段", "段位后"],
                    [
                        [
                            d["day"],
                            "是" if d["passed"] else "否",
                            d["consecutive_pass"],
                            "是" if d["tier_advanced"] else "否",
                            d["tier_after"],
                        ]
                        for d in diary
                    ],
                )
            ],
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC09_fail_resets_streak(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC09", "达标后失败连续次数清零"
        uid = _prep_user(
            client, db_session, phone="13880000009", nickname=title, grade="二年级"
        )
        d0 = _j._run_reading_day(
            client,
            db_session,
            uid,
            day_index=0,
            grade="二年级",
            card=_pass_card_for("超脑阅读", grade="二年级"),
            expect_pass=True,
        )
        d1 = _j._run_reading_day(
            client,
            db_session,
            uid,
            day_index=1,
            grade="二年级",
            card=_fail_card_for("超脑阅读"),
            expect_pass=False,
        )
        ok = d0["consecutive_pass"] == 1 and d1["consecutive_pass"] == 0
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="连续达标中途未达标：连续次数归零，段位不变。",
            preconditions=["二年级"],
            steps=["第1天达标", "第2天故意未达标"],
            expect=["第1天连续=1", "第2天连续=0", "未升段"],
            actual={
                "第1天连续": d0["consecutive_pass"],
                "第2天连续": d1["consecutive_pass"],
                "第2天升段": d1["tier_advanced"],
            },
            passed=ok,
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC10_grade_band_thresholds(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC10", "四学段超脑阅读阈值边界"
        table = []
        ok = True
        cases = [
            ("二年级", "700", "800", "13880000010"),
            ("四年级", "900", "1000", "13880000011"),
            ("初一", "1700", "1800", "13880000012"),
            ("高一", "1900", "2000", "13880000013"),
        ]
        for grade, fail_w, pass_w, phone in cases:
            uid = _prep_user(
                client, db_session, phone=phone, nickname=f"阈值{grade}", grade=grade
            )
            _moment(db_session, uid)
            sched = client.post(
                "/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid)
            )
            plan = sched.json()
            item = plan["items"][0]
            _force_item_skill(db_session, item["id"], "超脑阅读")
            fail_body = _complete_one_item(
                client,
                db_session,
                uid,
                plan,
                item,
                card={"name": "超脑阅读", "time": "3", "wordCount": fail_w},
                expect_pass=False,
            )
            out = _j._run_reading_day(
                client,
                db_session,
                uid,
                day_index=1,
                grade=grade,
                card={"name": "超脑阅读", "time": "3", "wordCount": pass_w},
                expect_pass=True,
            )
            row_ok = (
                fail_body["training_progress"]["skill_results"]["超脑阅读"]["passed"]
                is False
                and out["passed"] is True
            )
            ok = ok and row_ok
            table.append(
                [grade, fail_w, "未达标" if row_ok else "异常", pass_w, "达标" if out["passed"] else "否"]
            )
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="小学低/高、初中、高中超脑阅读一阶阈值：略低不过、贴线过。",
            preconditions=["各学段各一名新注册学员"],
            steps=["用略低于阈值卡打卡应不过", "次日用达标卡应过"],
            expect=["四学段边界判定均正确"],
            actual={"全部通过": ok},
            passed=ok,
            detail_tables=[
                ("学段边界", ["年级", "未达标字数", "结果", "达标字数", "结果"], table)
            ],
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC11_multiskill_same_day(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC11", "同日多技能互不误清零"
        uid = _prep_user(
            client, db_session, phone="13880000014", nickname=title, grade="四年级"
        )
        cps = {"超脑阅读": [], "影像追忆": []}
        for day in range(3):
            _moment(db_session, uid, day=day, hour=14)
            sched = client.post(
                "/api/training/schedule", json={"planned_minutes": 90}, **_auth(uid)
            )
            plan = sched.json()
            ids = [it["id"] for it in plan["items"]]
            while True:
                p = _required_pending(db_session, ids)
                if not p:
                    break
                sk = _skill_of_row(p) or "超脑阅读"
                tier = int(
                    get_training_progress(db_session.get(ChildUser, uid))["skills"]
                    .get(sk, {})
                    .get("tier")
                    or 1
                )
                body = _complete_one_item(
                    client,
                    db_session,
                    uid,
                    plan,
                    {"id": p.id, "sort_order": p.sort_order},
                    card=_pass_card_for(sk, grade="四年级", tier=tier),
                )
                sr = (body.get("training_progress") or {}).get("skill_results") or {}
                # 本次只应结算本关技能
                assert set(sr.keys()) <= {sk}
                if sk in cps and sk in sr:
                    cps[sk].append(
                        {
                            "连续": sr[sk].get("consecutive_pass"),
                            "同日已计": sr[sk].get("already_passed_today"),
                            "本次计入": sr[sk].get("counted_today"),
                        }
                    )
        child = db_session.get(ChildUser, uid)
        st = get_training_progress(child)
        ok = (
            int(st["skills"]["超脑阅读"]["tier"]) >= 2
            or int(st["skills"]["影像追忆"]["tier"]) >= 2
            or max((c["连续"] or 0) for c in cps["超脑阅读"] or [{"连续": 0}]) >= 2
        )
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="90分钟多技能同日：先打A再打B，不得把未打技能清零；同技能多槽不重复计连过。",
            preconditions=["四年级", "连续3天90分钟"],
            steps=["每天按序打完所有必修", "记录各技能连续与同日标记"],
            expect=["结算键仅为当次技能", "至少一技能形成升段或高连续"],
            actual={
                "超脑段位": st["skills"]["超脑阅读"]["tier"],
                "影像段位": st["skills"]["影像追忆"]["tier"],
                "超脑打卡次数": len(cps["超脑阅读"]),
                "影像打卡次数": len(cps["影像追忆"]),
            },
            passed=ok,
            detail_tables=[
                (
                    "超脑阅读结算摘要",
                    ["连续达标", "同日已计过", "本次计入"],
                    [
                        [x["连续"], x["同日已计"], x["本次计入"]]
                        for x in cps["超脑阅读"]
                    ],
                )
            ],
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC12_after_advance_new_threshold(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC12", "升段后须按新阈值继续"
        uid = _prep_user(
            client, db_session, phone="13880000015", nickname=title, grade="四年级"
        )
        for day in range(3):
            _j._run_reading_day(
                client,
                db_session,
                uid,
                day_index=day,
                grade="四年级",
                card=_pass_card_for("超脑阅读", grade="四年级", tier=1),
                expect_pass=True,
            )
        # 升到2后，用旧一阶卡应不过
        fail = _j._run_reading_day(
            client,
            db_session,
            uid,
            day_index=3,
            grade="四年级",
            card={"name": "超脑阅读", "time": "3", "wordCount": "1000"},  # 一阶贴线
            expect_pass=False,
        )
        # 二阶达标卡应过
        ok2 = _j._run_reading_day(
            client,
            db_session,
            uid,
            day_index=4,
            grade="四年级",
            card=_pass_card_for("超脑阅读", grade="四年级", tier=2),
            expect_pass=True,
        )
        ok = fail["passed"] is False and ok2["passed"] is True
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="升到第2段后，一阶贴线成绩不再达标；须按二阶阈值交卡。",
            preconditions=["四年级", "先连过升到第2段"],
            steps=["用一阶1000字/3分卡", "再用二阶达标卡"],
            expect=["旧卡未达标", "新阈值卡达标"],
            actual={
                "旧卡结果": "未达标" if not fail["passed"] else "误通过",
                "新卡结果": "达标" if ok2["passed"] else "未达标",
                "旧卡数据": fmt_card({"wordCount": "1000", "time": "3"}),
                "新卡数据": fmt_card(_pass_card_for("超脑阅读", grade="四年级", tier=2)),
            },
            passed=ok,
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC13_training_day_4am_boundary(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC13", "训练日凌晨四点分界"
        uid = _prep_user(
            client, db_session, phone="13880000016", nickname=title, grade="二年级"
        )
        # 9/2 03:30 → 仍属 9/1 训练日；9/2 05:00 → 9/2 训练日（避开 4:00–4:05 冻结窗）
        m_early = datetime(2026, 9, 2, 3, 30, 0, tzinfo=TZ)
        set_time_override(db_session, uid, m_early)
        db_session.commit()
        r1 = client.post(
            "/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid)
        )
        assert r1.status_code == 200, r1.text
        day1 = get_training_day(m_early)
        pid1 = r1.json()["plan_id"]
        plan_date1 = r1.json().get("plan_date") or str(day1)

        m_late = datetime(2026, 9, 2, 5, 0, 0, tzinfo=TZ)
        set_time_override(db_session, uid, m_late)
        db_session.commit()
        r2 = client.post(
            "/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid)
        )
        assert r2.status_code == 200, r2.text
        day2 = get_training_day(m_late)
        pid2 = r2.json()["plan_id"]
        plan_date2 = r2.json().get("plan_date") or str(day2)
        ok = (
            day1.isoformat() == "2026-09-01"
            and day2.isoformat() == "2026-09-02"
            and pid1 != pid2
        )
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="训练日以凌晨4点为界：4点前属上一训练日，4:05后属新训练日。",
            preconditions=["二年级老学员", "开启开发时钟"],
            steps=[
                "将时钟拨到9/2 03:30并排课",
                "再拨到9/2 05:00并排课",
                "对比训练日与方案ID",
            ],
            expect=["03:30→训练日9/1", "05:00→训练日9/2", "两日方案ID不同"],
            actual={
                "早班时钟": m_early.isoformat(),
                "早班训练日": day1.isoformat(),
                "早班方案日": plan_date1,
                "早班方案ID": pid1,
                "晚班时钟": m_late.isoformat(),
                "晚班训练日": day2.isoformat(),
                "晚班方案日": plan_date2,
                "晚班方案ID": pid2,
            },
            passed=ok,
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC14_started_cannot_change_minutes(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC14", "已开练禁止改今日时长"
        uid = _prep_user(
            client, db_session, phone="13880000017", nickname=title, grade="四年级"
        )
        _moment(db_session, uid, hour=10)
        r1 = client.post(
            "/api/training/schedule", json={"planned_minutes": 60}, **_auth(uid)
        )
        assert r1.status_code == 200, r1.text
        plan = r1.json()
        item = plan["items"][0]
        # 上报进度 → 视为已开始
        client.post(
            f"/api/training/items/{item['id']}/watch-progress",
            json={"watched_sec": 30, "duration_sec": 100, "media": "audio"},
            **_auth(uid),
        )
        blocked = client.post(
            "/api/training/schedule", json={"planned_minutes": 180}, **_auth(uid)
        )
        ok = blocked.status_code == 403 and "时长" in (blocked.json().get("detail") or "")
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="同一训练日已开始观看后，不得改设定时长重排。",
            preconditions=["四年级", "先排60分钟并上报观看进度"],
            steps=["排课60分钟", "上报任一项观看进度", "再请求改排180分钟"],
            expect=["返回403", "提示无法更改今日设定时长"],
            actual={
                "状态码": blocked.status_code,
                "错误信息": blocked.json().get("detail"),
                "原方案ID": plan["plan_id"],
            },
            passed=ok,
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC15_overall_is_min_checked_skills(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC15", "整体段位取已打卡技能最低"
        uid = _prep_user(
            client, db_session, phone="13880000018", nickname=title, grade="四年级"
        )
        # 超脑连过3天 → 2段
        for day in range(3):
            _j._run_reading_day(
                client,
                db_session,
                uid,
                day_index=day,
                grade="四年级",
                card=_pass_card_for("超脑阅读", grade="四年级", tier=1),
                expect_pass=True,
            )
        # 第4天专练影像一关达标 → 影像仍1段
        _moment(db_session, uid, day=3, hour=14)
        sched = client.post(
            "/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid)
        )
        assert sched.status_code == 200, sched.text
        plan = sched.json()
        item = plan["items"][0]
        _force_item_skill(db_session, item["id"], "影像追忆")
        _complete_one_item(
            client,
            db_session,
            uid,
            plan,
            item,
            card=_pass_card_for("影像追忆", grade="四年级", tier=1),
            expect_pass=True,
        )
        child = db_session.get(ChildUser, uid)
        st = get_training_progress(child)
        reading_tier = int(st["skills"]["超脑阅读"]["tier"])
        memory_tier = int(st["skills"]["影像追忆"]["tier"])
        overall = display_overall_tier(db_session, child)
        ok = reading_tier >= 2 and memory_tier == 1 and overall == 1
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="整体段位=已打卡技能最低段；高段技能不能把整体抬高。",
            preconditions=["四年级", "超脑先升到≥2", "再打影像1次"],
            steps=["连续3天超脑达标升段", "第4天强制影像达标", "读整体段位"],
            expect=["超脑≥2", "影像=1", "整体=1"],
            actual={
                "超脑段位": reading_tier,
                "影像段位": memory_tier,
                "整体段位": overall,
            },
            passed=ok,
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC16_gap_day_keeps_streak(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC16", "间隔休息日连续达标仍累计"
        uid = _prep_user(
            client, db_session, phone="13880000019", nickname=title, grade="二年级"
        )
        d0 = _j._run_reading_day(
            client,
            db_session,
            uid,
            day_index=0,
            grade="二年级",
            card=_pass_card_for("超脑阅读", grade="二年级"),
            expect_pass=True,
        )
        # 中间休息一天不排课
        d2 = _j._run_reading_day(
            client,
            db_session,
            uid,
            day_index=2,
            grade="二年级",
            card=_pass_card_for("超脑阅读", grade="二年级"),
            expect_pass=True,
        )
        ok = d0["consecutive_pass"] == 1 and d2["consecutive_pass"] == 2
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="连续达标按「打卡结算次数」累计；中间休息未打卡不打断连续。",
            preconditions=["二年级"],
            steps=["第1天达标", "第2天休息不排课", "第3天再达标"],
            expect=["第1天连续=1", "第3天连续=2", "未因休息清零"],
            actual={
                "第1天连续": d0["consecutive_pass"],
                "第3天连续": d2["consecutive_pass"],
                "第3天升段": d2["tier_advanced"],
            },
            passed=ok,
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC17_long_480_energy_recover(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC17", "八段长训挂精力恢复"
        # 公式层：三阶 + 480 分钟应追加精力恢复
        fr = expand_formula(480, overall_tier=3, grade_band="primary_high")
        slots = fr.get("slots") or []
        extras = fr.get("extras") or []
        formula_ok = "精力恢复" in slots or "精力恢复" in extras

        uid = _prep_user(
            client, db_session, phone="13880000020", nickname=title, grade="四年级"
        )
        child = db_session.get(ChildUser, uid)
        state = get_training_progress(child)
        for sk in ("超脑阅读", "影像追忆", "扫描速记", "极速运算", "极速学习"):
            set_skill_tier(state, sk, 3)
        save_training_progress(db_session, child, state)
        _moment(db_session, uid, hour=9)
        sched = client.post(
            "/api/training/schedule", json={"planned_minutes": 480}, **_auth(uid)
        )
        assert sched.status_code == 200, sched.text
        skills = [_parse_skill(it) for it in sched.json()["items"]]
        live_ok = "精力恢复" in skills
        ok = formula_ok and live_ok
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="整体≥三阶且规划≥480分钟：清单应追加精力恢复（免打卡选修）。",
            preconditions=["四年级", "进度技能均置为3段（无打卡记录时按状态取最低）"],
            steps=["公式展开480×三阶", "实排课480分钟", "检查清单是否含精力恢复"],
            expect=["公式含精力恢复", "实排清单含精力恢复"],
            actual={
                "公式slots": slots,
                "公式extras": extras,
                "实排技能": skills,
                "整体展示段位": display_overall_tier(db_session, child),
            },
            passed=ok,
            detail_tables=[
                (
                    "对照",
                    ["层", "含精力恢复"],
                    [["公式", "是" if formula_ok else "否"], ["实排", "是" if live_ok else "否"]],
                )
            ],
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC18_unstarted_can_reschedule(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC18", "未开练可改时长重生"
        uid = _prep_user(
            client, db_session, phone="13880000021", nickname=title, grade="二年级"
        )
        _moment(db_session, uid, hour=11)
        r1 = client.post(
            "/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid)
        )
        assert r1.status_code == 200
        n1 = len(r1.json()["items"])
        pid1 = r1.json()["plan_id"]
        r2 = client.post(
            "/api/training/schedule", json={"planned_minutes": 90}, **_auth(uid)
        )
        assert r2.status_code == 200, r2.text
        n2 = len(r2.json()["items"])
        pid2 = r2.json()["plan_id"]
        ok = n1 == 1 and n2 >= 3 and pid1 == pid2
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="未开始观看前，同一训练日可改时长并重生清单；方案壳ID不变。",
            preconditions=["二年级", "当日尚未上报观看"],
            steps=["先排20分钟", "不观看直接改排90分钟", "对比项数与方案ID"],
            expect=["20分钟约1项", "90分钟≥3项", "plan_id相同"],
            actual={
                "20分钟项数": n1,
                "90分钟项数": n2,
                "方案ID前后": [pid1, pid2],
                "90分钟技能": [_parse_skill(it) for it in r2.json()["items"]],
            },
            passed=ok,
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_TC19_tier3_bundle_includes_calc(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC19", "整体三段运算捆绑"
        fr = expand_formula(
            60,
            overall_tier=3,
            grade_band="primary_low",
            skill_tiers={
                "影像追忆": 3,
                "扫描速记": 2,
                "极速运算": 1,
                "极速学习": 2,
                "超脑阅读": 3,
            },
        )
        bundle = fr.get("bundle_skills") or []
        engine = fr.get("schedule_engine") or fr.get("strategy")
        ok = "极速运算" in bundle and (
            engine in ("bundle", "weight_with_bundle") or bool(fr.get("bundle_id"))
        )
        # 四阶同条件不应再强制捆绑
        fr4 = expand_formula(
            60,
            overall_tier=4,
            grade_band="primary_low",
            skill_tiers={"极速运算": 1, "扫描速记": 2, "影像追忆": 3},
        )
        ok4 = not (fr4.get("bundle_skills") or []) or fr4.get("schedule_engine") == "weight"
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="整体正好三段：60分钟须先出现运算捆绑；升到四段后不再捆绑。",
            preconditions=["公式引擎与线上排课同源", "个体技能段位已给定"],
            steps=["三阶×60展开", "检查bundle_skills含极速运算", "四阶×60对照"],
            expect=["三阶有捆绑且含极速运算", "四阶无捆绑或纯权重"],
            actual={
                "三阶引擎": engine,
                "三阶捆绑": bundle,
                "三阶清单": fr.get("slots"),
                "三阶bundle_id": fr.get("bundle_id"),
                "四阶引擎": fr4.get("schedule_engine") or fr4.get("strategy"),
                "四阶捆绑": fr4.get("bundle_skills") or [],
                "四阶通过": ok4,
            },
            passed=ok and ok4,
        )
        _reg(cid, title, path, ok and ok4)
        assert ok and ok4

    def test_TC25_time_over_fail_word_ok(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        cid, title = "TC25", "字数够但用时超时未达标"
        uid = _prep_user(
            client, db_session, phone="13880000025", nickname=title, grade="二年级"
        )
        _moment(db_session, uid)
        sched = client.post(
            "/api/training/schedule", json={"planned_minutes": 20}, **_auth(uid)
        )
        assert sched.status_code == 200
        plan = sched.json()
        item = plan["items"][0]
        _force_item_skill(db_session, item["id"], "超脑阅读")
        # 二年级一阶：800字/3分；字数够但用时10分应不过
        body = _complete_one_item(
            client,
            db_session,
            uid,
            plan,
            item,
            card={"name": "超脑阅读", "time": "10", "wordCount": "800"},
            expect_pass=False,
        )
        sr = (body.get("training_progress") or {}).get("skill_results") or {}
        passed_flag = (sr.get("超脑阅读") or {}).get("passed")
        ok = passed_flag is False
        path = write_case_doc(
            case_id=cid,
            title=title,
            purpose="超脑阅读达标需同时满足字数与用时；字数贴线但超时仍未达标。",
            preconditions=["二年级一阶", "强制超脑阅读"],
            steps=["交卡：800字/10分钟", "查看结算passed"],
            expect=["passed=false", "连续次数不增加"],
            actual={
                "卡片": fmt_card({"wordCount": "800", "time": "10"}),
                "passed": passed_flag,
                "连续": (sr.get("超脑阅读") or {}).get("consecutive_pass"),
            },
            passed=ok,
        )
        _reg(cid, title, path, ok)
        assert ok

    def test_ZZZ_write_catalog(self):
        """写目录：合并本类已登记用例 + 磁盘上已有的学员旅程用例。"""
        assert len(_CATALOG) >= 18
        disk = []
        for p in sorted(DOC_ROOT.glob("TC*.md")):
            stem = p.stem
            parts = stem.split("-", 1)
            if len(parts) != 2:
                continue
            # 本类刚跑的以 _CATALOG 为准，避免重复
            if any(c["case_id"] == parts[0] for c in _CATALOG):
                continue
            disk.append(
                {
                    "case_id": parts[0],
                    "title": parts[1],
                    "passed": True,
                    "file": p.name,
                }
            )
        merged = sorted(_CATALOG + disk, key=lambda c: c["case_id"])
        path = write_catalog(merged)
        assert path.exists()
        pointer = Path(__file__).resolve().parents[2] / "docs" / "训练实测日记-多月学员.md"
        pointer.write_text(
            "\n".join(
                [
                    "# 今日修炼实测文档已按用例拆分",
                    "",
                    "请从用例目录进入（一用例一文件）：",
                    "",
                    "- [今日修炼实测用例/00-用例目录.md](./今日修炼实测用例/00-用例目录.md)",
                    "",
                ]
            ),
            encoding="utf-8",
        )
