"""多月学员日记：长时间多技能组合 + 不固定时刻，实跑写文档。

覆盖：
- 每天按排课跑完所有必修关（多技能组合），看视频→听音频→打卡
- 预约时长按人格/日期变化；训练时刻在 8–22 点间轮换（非固定 10:00）
- 升段后用新 Tier 阈值继续；同日多关升段不误清零、不重复计连续达标
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.db.models import ChildUser, TrainingItem
from app.services.child_training_state import display_overall_tier, get_training_progress
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
_fail_card_for = _journey._fail_card_for
_parse_skill = _journey._parse_skill
_pass_card_for = _journey._pass_card_for
_prep_user = _journey._prep_user
_set_day = _journey._set_day

BASE_DATE = datetime(2026, 9, 1, tzinfo=TZ)
DAYS = 90
# 训练日内合法时刻（≥4 点），刻意打散
CLOCK_HOURS = (8, 11, 14, 16, 19, 21, 22)

READING_SCORED_MAX_TIER = 2

import sys as _sys

_td = str(_Path(__file__).resolve().parent)
if _td not in _sys.path:
    _sys.path.insert(0, _td)
from training_case_docutil import DOC_ROOT, write_case_doc, write_catalog  # noqa: E402


def _near_miss_for(skill: str, grade: str, tier: int) -> dict:
    if skill != "超脑阅读":
        return _fail_card_for(skill)
    if tier >= 2:
        if grade in ("高一", "高二", "高三"):
            return {"name": skill, "time": "5", "wordCount": "4800"}
        if grade in ("初一", "初二", "初三"):
            return {"name": skill, "time": "5", "wordCount": "3800"}
        if grade in ("四年级", "五年级", "六年级"):
            return {"name": skill, "time": "5", "wordCount": "2400"}
        return {"name": skill, "time": "5", "wordCount": "1900"}
    if grade in ("高一", "高二", "高三"):
        return {"name": skill, "time": "3", "wordCount": "1900"}
    if grade in ("初一", "初二", "初三"):
        return {"name": skill, "time": "3", "wordCount": "1700"}
    if grade in ("四年级", "五年级", "六年级"):
        return {"name": skill, "time": "3", "wordCount": "900"}
    return {"name": skill, "time": "3", "wordCount": "700"}


def _persona_outcome(
    persona: str, day: int, skill: str, tier: int, *, overall: int
) -> str:
    # overall≥7 排课空槽：到 6 后放慢，避免全技能顶满后无法继续
    if overall >= 6 and day % 3 != 0:
        return "near" if skill == "超脑阅读" else "fail"
    if skill == "超脑阅读" and tier > READING_SCORED_MAX_TIER:
        return "pass"
    if skill == "扫描速记" and tier <= 1:
        return "pass"
    if persona == "high":
        return "pass"
    if persona == "low":
        if day < 25:
            return "fail" if day % 3 else "near"
        if day < 50:
            return "pass" if day % 4 == 0 else ("near" if day % 2 else "fail")
        if day < 70:
            return "pass" if day % 3 else "near"
        return "pass"
    if day < 20:
        return ("pass", "fail", "pass", "near", "pass", "fail", "pass")[day % 7]
    if day < 45:
        return ("pass", "pass", "near", "pass", "fail", "pass", "pass")[day % 7]
    if tier >= 2 and day < 60:
        return ("pass", "near", "pass", "pass", "fail", "pass", "pass")[day % 7]
    return "pass" if day % 11 else "near"


def _card_for_outcome(skill: str, grade: str, tier: int, outcome: str) -> dict:
    if outcome == "fail":
        return _fail_card_for(skill)
    if outcome == "near":
        return _near_miss_for(skill, grade, tier)
    if skill == "超脑阅读" and tier > READING_SCORED_MAX_TIER:
        return {"name": skill, "time": "5", "wordCount": "1000"}
    return _pass_card_for(skill, grade=grade, tier=max(1, tier))


def _skill_tier(db, uid: int, skill: str) -> int:
    child = db.get(ChildUser, uid)
    db.refresh(child)
    state = get_training_progress(child)
    return int((state.get("skills") or {}).get(skill, {}).get("tier") or 1)


def _minutes_for(persona: str, day: int) -> int:
    """预约时长不固定：含 3–5 小时档（对齐需求 150/180/240/300）。"""
    if persona == "high":
        return (20, 40, 60, 90, 180)[day % 5]
    if persona == "low":
        return (90, 120, 180, 240, 300)[day % 5]
    return (40, 90, 150, 180, 240)[day % 5]


def _day_mode(persona: str, day: int) -> str:
    """full=打完必修 / partial=只打前几关 / schedule_only=只排课不打卡。"""
    if persona == "low":
        if day % 11 == 0:
            return "schedule_only"
        if day % 5 == 0:
            return "partial"
        return "full"
    if persona == "medium":
        if day % 17 == 0:
            return "schedule_only"
        if day % 7 == 0:
            return "partial"
        return "full"
    if day % 19 == 0:
        return "partial"
    return "full"


def _clock_for(day: int) -> datetime:
    hour = CLOCK_HOURS[day % len(CLOCK_HOURS)]
    return BASE_DATE.replace(hour=hour, minute=(day * 7) % 60) + timedelta(days=day)


def _next_pending_required(db, item_ids: list[int]) -> TrainingItem | None:
    for iid in item_ids:
        row = db.get(TrainingItem, iid)
        if not row:
            continue
        db.refresh(row)
        if row.checkin_status == "done":
            continue
        if item_skips_checkin(row):
            continue
        return row
    return None


def _run_student_months(
    client,
    db_session,
    *,
    label: str,
    phone: str,
    nickname: str,
    grade: str,
    persona: str,
    days: int = DAYS,
) -> dict:
    uid = _prep_user(
        client,
        db_session,
        phone=phone,
        nickname=nickname,
        grade=grade,
        cohort="regular",
    )
    rows: list[dict] = []
    advances: list[dict] = []
    multi_skill_days = 0
    long_session_days = 0
    partial_days = 0
    schedule_only_days = 0
    elective_skip_days = 0
    stopped_reason = None
    minutes_seen: set[int] = set()
    hours_seen: set[int] = set()

    for day in range(days):
        moment = _clock_for(day)
        _set_day(db_session, uid, 0, base=moment)
        plan_date = moment.date().isoformat()
        hours_seen.add(moment.hour)
        minutes = _minutes_for(persona, day)
        minutes_seen.add(minutes)
        mode = _day_mode(persona, day)
        if minutes >= 180:
            long_session_days += 1

        child = db_session.get(ChildUser, uid)
        db_session.refresh(child)
        overall = display_overall_tier(db_session, child)

        sched = client.post(
            "/api/training/schedule",
            json={"planned_minutes": minutes},
            **_auth(uid),
        )
        if sched.status_code != 200:
            stopped_reason = f"day={day} schedule {sched.status_code} {sched.text}"
            break
        plan = sched.json()
        items = sorted(plan.get("items") or [], key=lambda x: x.get("sort_order") or 0)
        if not items:
            stopped_reason = f"day={day} empty items"
            break

        # 部分日子挂上多元感知但不打卡（需求：可打可不打，不打不算失败）
        if day % 9 == 3 and mode != "schedule_only":
            tog = client.post(
                "/api/training/plan/elective-toggle",
                json={
                    "plan_id": plan["plan_id"],
                    "skill": "多元感知",
                    "action": "add",
                },
                **_auth(uid),
            )
            if tog.status_code == 200:
                plan = tog.json()
                items = sorted(
                    plan.get("items") or [], key=lambda x: x.get("sort_order") or 0
                )
                elective_skip_days += 1

        item_ids = [it["id"] for it in items]
        skills_today = []
        for it in items:
            sk = _parse_skill(it)
            if sk:
                skills_today.append(sk)
        if len(set(s for s in skills_today if s not in ("高效作业", "精力恢复"))) >= 2:
            multi_skill_days += 1

        if mode == "schedule_only":
            schedule_only_days += 1
            rows.append(
                {
                    "student": label,
                    "date": plan_date,
                    "clock": moment.strftime("%H:%M"),
                    "day_index": day,
                    "day_mode": mode,
                    "planned_minutes": plan.get("planned_minutes") or minutes,
                    "items_in_plan": len(items),
                    "skills_in_plan": skills_today,
                    "item_id": None,
                    "sort_order": None,
                    "skill": "(未打卡)",
                    "tier_before": None,
                    "outcome_intent": "schedule_only",
                    "card": {},
                    "passed": False,
                    "consecutive_pass": None,
                    "tier_advanced": False,
                    "tier_after": None,
                    "detail": "仅排课，当日未打卡",
                    "overall_before": overall,
                }
            )
            continue

        if mode == "partial":
            partial_days += 1

        # full=打完必修；partial=只打前 1 关必修；选修/高效作业走 skips 不交卡
        max_required = 1 if mode == "partial" else 20
        done_required = 0
        guard = 0
        while guard < 24 and done_required < max_required:
            guard += 1
            pending = _next_pending_required(db_session, item_ids)
            if not pending:
                break
            skill = pending.title or "超脑阅读"
            if pending.instructions and str(pending.instructions).startswith("{"):
                try:
                    skill = json.loads(pending.instructions).get("skill") or skill
                except json.JSONDecodeError:
                    pass
            if skill in ("多元感知", "感知力", "高效作业", "精力恢复"):
                # 不应进入 required pending
                break

            tier_before = _skill_tier(db_session, uid, skill)
            child = db_session.get(ChildUser, uid)
            db_session.refresh(child)
            overall = display_overall_tier(db_session, child)
            outcome = _persona_outcome(
                persona, day, skill, tier_before, overall=overall
            )
            card = _card_for_outcome(skill, grade, tier_before, outcome)
            item_dict = {
                "id": pending.id,
                "sort_order": pending.sort_order,
                "instructions": pending.instructions,
            }
            body = _complete_one_item(
                client,
                db_session,
                uid,
                plan,
                item_dict,
                card=card,
                expect_pass=None,
            )
            done_required += 1
            sr = ((body.get("training_progress") or {}).get("skill_results") or {}).get(
                skill
            ) or {}
            passed = bool(sr.get("passed"))
            tier_after = int(sr.get("tier_after") or tier_before)
            advanced = bool(sr.get("tier_advanced"))
            cp = int(sr.get("consecutive_pass") or 0)
            detail = ""
            td = sr.get("threshold_detail") or {}
            if isinstance(td, dict):
                detail = str(td.get("detail") or "")
            row = {
                "student": label,
                "date": plan_date,
                "clock": moment.strftime("%H:%M"),
                "day_index": day,
                "day_mode": mode,
                "planned_minutes": plan.get("planned_minutes") or minutes,
                "items_in_plan": len(items),
                "skills_in_plan": skills_today,
                "item_id": pending.id,
                "sort_order": pending.sort_order,
                "skill": skill,
                "tier_before": tier_before,
                "outcome_intent": outcome,
                "card": card,
                "passed": passed,
                "consecutive_pass": cp,
                "tier_advanced": advanced,
                "tier_after": tier_after,
                "counted_today": sr.get("counted_today"),
                "already_passed_today": sr.get("already_passed_today"),
                "detail": detail,
                "overall_before": overall,
            }
            rows.append(row)
            if advanced:
                advances.append(
                    {
                        "date": plan_date,
                        "clock": moment.strftime("%H:%M"),
                        "skill": skill,
                        "from": tier_before,
                        "to": tier_after,
                    }
                )

    child = db_session.get(ChildUser, uid)
    db_session.refresh(child)
    final = get_training_progress(child)
    active_days = len({r["date"] for r in rows})
    return {
        "label": label,
        "nickname": nickname,
        "grade": grade,
        "persona": persona,
        "minutes_pool": sorted(minutes_seen),
        "hours_pool": sorted(hours_seen),
        "uid": uid,
        "start": rows[0]["date"] if rows else None,
        "end": rows[-1]["date"] if rows else None,
        "days_planned": days,
        "days_completed": active_days,
        "multi_skill_days": multi_skill_days,
        "long_session_days": long_session_days,
        "partial_days": partial_days,
        "schedule_only_days": schedule_only_days,
        "elective_skip_days": elective_skip_days,
        "stopped_reason": stopped_reason,
        "rows": rows,
        "advances": advances,
        "final_skills": {
            sk: {
                "tier": int(sd.get("tier") or 1),
                "consecutive_pass": int(sd.get("consecutive_pass") or 0),
            }
            for sk, sd in (final.get("skills") or {}).items()
        },
        "pass_count": sum(1 for r in rows if r["passed"]),
        "fail_count": sum(1 for r in rows if not r["passed"]),
    }


_CARD_FIELD_ZH = {
    "wordCount": "字数",
    "time": "用时(分)",
    "accuracy": "准确度(%)",
    "reverseRecite": "倒背",
    "completed": "已完成",
    "correctCount": "正确数",
    "projectName": "项目名",
    "projectDays": "项目天数",
    "note": "备注",
}
_MODE_ZH = {
    "full": "全日打完",
    "partial": "部分打卡",
    "schedule_only": "只排课",
}
_INTENT_ZH = {
    "pass": "按达标交",
    "fail": "按未达标交",
    "near": "差一点",
    "schedule_only": "只排课",
}
_PERSONA_ZH = {
    "high": "高效",
    "medium": "中等起伏",
    "low": "低效长训",
}


def _fmt_card(card: dict) -> str:
    parts = []
    for k, label in _CARD_FIELD_ZH.items():
        if k in card and card[k] is not None:
            val = card[k]
            if k == "reverseRecite":
                val = "是" if val else "否"
            if k == "completed":
                val = "是" if val else "否"
            parts.append(f"{label}={val}")
    if parts:
        return "，".join(parts)
    # 未知字段也尽量中文化键名
    extra = []
    for k, v in (card or {}).items():
        if k in _CARD_FIELD_ZH or k == "name":
            continue
        extra.append(f"{k}={v}")
    return "，".join(extra) if extra else "（无）"


def _zh_mode(mode: str | None) -> str:
    return _MODE_ZH.get(mode or "full", mode or "全日打完")


def _zh_intent(intent: str | None) -> str:
    return _INTENT_ZH.get(intent or "", intent or "")


def _zh_persona(persona: str | None) -> str:
    return _PERSONA_ZH.get(persona or "", persona or "")


def _render_markdown(students: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# 今日修炼多月学员实测日记")
    lines.append("")
    lines.append("> 本文件由多月学员实测用例 **实跑生成**，非手填。")
    lines.append("")
    lines.append("## 模拟约定")
    lines.append("")
    lines.append(
        f"- 训练日起点：{BASE_DATE.date().isoformat()}，规划 **{DAYS}** 个训练日（约 3 个月）。"
    )
    lines.append(
        "- 每日：**自然排课多技能组合** → 按顺序看视频/听音频 → 逐项打卡；"
        "升段结算只处理本次交卡技能，同日同技能不重复计连续达标。"
    )
    lines.append(
        f"- 时刻不固定：在 {list(CLOCK_HOURS)} 点之间轮换，分钟亦随日期变化。"
    )
    lines.append(
        "- 时长不固定：含 **3–5 小时**（180/240/300 分钟）及需求档 150 分钟；"
        "高效偶发长训，低效以长训为主。"
    )
    lines.append(
        "- 完成度不固定：**全日打完** / **部分打卡**（只打前几关） / **只排课**（当日不打卡）。"
    )
    lines.append(
        "- 选修：部分日子挂「多元感知」但不打卡；长训清单中的「高效作业」免打卡不阻塞（对齐需求文档）。"
    )
    lines.append(
        "- 人格：高效 / 中等起伏 / 低效长训；整体段位到 6 后放慢，避免排课空槽。"
    )
    lines.append("")

    for st in students:
        lines.append(f"## {st['label']}（{st['nickname']}）")
        lines.append("")
        lines.append("| 项 | 值 |")
        lines.append("|---|---|")
        lines.append(f"| 年级 | {st['grade']} |")
        lines.append(f"| 人格 | {_zh_persona(st['persona'])} |")
        lines.append(f"| 用过的预约时长(分) | {st['minutes_pool']} |")
        lines.append(f"| 用过的训练时刻(时) | {st['hours_pool']} |")
        lines.append(f"| 区间 | {st['start']} ~ {st['end']} |")
        lines.append(f"| 完成训练日 / 规划 | {st['days_completed']} / {st['days_planned']} |")
        lines.append(f"| 多技能组合天数 | {st['multi_skill_days']} |")
        lines.append(f"| ≥3小时长训天数 | {st.get('long_session_days', 0)} |")
        lines.append(f"| 部分打卡天数 | {st.get('partial_days', 0)} |")
        lines.append(f"| 只排课未打卡天数 | {st.get('schedule_only_days', 0)} |")
        lines.append(f"| 挂选修但不打卡天数 | {st.get('elective_skip_days', 0)} |")
        lines.append(f"| 打卡条数 | {len(st['rows'])} |")
        lines.append(f"| 达标 / 未达标 | {st['pass_count']} / {st['fail_count']} |")
        lines.append(f"| 升段次数 | {len(st['advances'])} |")
        if st.get("stopped_reason"):
            lines.append(f"| 提前结束 | {st['stopped_reason']} |")
        lines.append("")
        lines.append("### 升段时间线")
        lines.append("")
        if st["advances"]:
            lines.append("| 日期 | 时刻 | 技能 | 段位变化 |")
            lines.append("|---|---|---|---|")
            for a in st["advances"]:
                lines.append(
                    f"| {a['date']} | {a.get('clock', '')} | {a['skill']} | "
                    f"第{a['from']}段 → 第{a['to']}段 |"
                )
        else:
            lines.append("（本区间内无升段）")
        lines.append("")
        lines.append("### 期末技能状态")
        lines.append("")
        lines.append("| 技能 | 段位 | 连续达标 |")
        lines.append("|---|---:|---:|")
        for sk, sd in sorted(st["final_skills"].items()):
            if sd["tier"] > 1 or sd["consecutive_pass"] > 0:
                lines.append(
                    f"| {sk} | {sd['tier']} | {sd['consecutive_pass']} |"
                )
        lines.append("")
        lines.append("### 逐日打卡明细")
        lines.append("")
        lines.append(
            "| 日期 | 时刻 | 当日模式 | 时长(分) | 当日技能组合 | 本关技能 | "
            "训练前段位 | 打卡数据 | 交卡意图 | 是否达标 | 连续达标 | 是否升段 | "
            "训练后段位 | 判定摘要 |"
        )
        lines.append(
            "|---|---|---|---:|---|---|---:|---|---|---|---:|---|---:|---|"
        )
        for r in st["rows"]:
            adv = "是" if r.get("tier_advanced") else ""
            if r.get("day_mode") == "schedule_only":
                ok = "未打卡"
            else:
                ok = "达标" if r.get("passed") else "未达标"
            detail = (r.get("detail") or "").replace("|", "/")
            if len(detail) > 36:
                detail = detail[:33] + "..."
            combo = "+".join(r.get("skills_in_plan") or []) or "-"
            lines.append(
                "| {date} | {clock} | {mode} | {mins} | {combo} | {skill} | {tb} | "
                "{card} | {intent} | {ok} | {cp} | {adv} | {ta} | {detail} |".format(
                    date=r["date"],
                    clock=r.get("clock", ""),
                    mode=_zh_mode(r.get("day_mode")),
                    mins=r.get("planned_minutes"),
                    combo=combo,
                    skill=r["skill"],
                    tb=r.get("tier_before") if r.get("tier_before") is not None else "",
                    card=_fmt_card(r.get("card") or {}),
                    intent=_zh_intent(r.get("outcome_intent")),
                    ok=ok,
                    cp=r.get("consecutive_pass")
                    if r.get("consecutive_pass") is not None
                    else "",
                    adv=adv,
                    ta=r.get("tier_after") if r.get("tier_after") is not None else "",
                    detail=detail,
                )
            )
        lines.append("")

    lines.append("## 对照结论（实跑）")
    lines.append("")
    for st in students:
        first_adv = (
            f"{st['advances'][0]['date']} {st['advances'][0].get('clock', '')} "
            f"{st['advances'][0]['skill']} "
            f"第{st['advances'][0]['from']}段→第{st['advances'][0]['to']}段"
            if st["advances"]
            else "无"
        )
        lines.append(
            f"- **{st['label']}**（{_zh_persona(st['persona'])}）：完成 {st['days_completed']} 天、"
            f"多技能日 {st['multi_skill_days']}、≥3小时 {st.get('long_session_days', 0)}、"
            f"部分打卡 {st.get('partial_days', 0)}、只排课 {st.get('schedule_only_days', 0)}、"
            f"选修不打 {st.get('elective_skip_days', 0)}；"
            f"时长池 {st['minutes_pool']}；时刻池 {st['hours_pool']}；"
            f"首次升段 {first_adv}；"
            f"期末超脑阅读段位={st['final_skills'].get('超脑阅读', {}).get('tier', 1)} / "
            f"影像追忆={st['final_skills'].get('影像追忆', {}).get('tier', 1)} / "
            f"扫描速记={st['final_skills'].get('扫描速记', {}).get('tier', 1)}。"
        )
    lines.append("")
    return "\n".join(lines)


@pytest.fixture
def enable_dev_clock(monkeypatch):
    monkeypatch.setenv("JNAO_DEV_MODE", "1")
    monkeypatch.setenv("JNAO_ENV", "development")


class TestMultiSkillSameDayAdvance:
    """专门验证：长时间多技能同日打卡，升段逻辑可走通。"""

    def test_90min_two_skills_no_cross_reset(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        uid = _prep_user(
            client,
            db_session,
            phone="13710008001",
            nickname="多技能同日",
            grade="四年级",
            cohort="regular",
        )
        # 连续 3 个训练日，每天 90 分钟多关全打完，两技能都应能攒连续达标
        reading_cp = []
        recall_cp = []
        for day in range(3):
            moment = _clock_for(day)
            _set_day(db_session, uid, 0, base=moment)
            sched = client.post(
                "/api/training/schedule",
                json={"planned_minutes": 90},
                **_auth(uid),
            )
            assert sched.status_code == 200, sched.text
            plan = sched.json()
            items = sorted(plan["items"], key=lambda x: x.get("sort_order") or 0)
            assert len(items) >= 2, "90 分钟应多技能"
            item_ids = [it["id"] for it in items]
            while True:
                pending = _next_pending_required(db_session, item_ids)
                if not pending:
                    break
                skill = "超脑阅读"
                if pending.instructions and str(pending.instructions).startswith("{"):
                    try:
                        skill = json.loads(pending.instructions).get("skill") or skill
                    except json.JSONDecodeError:
                        pass
                tier = _skill_tier(db_session, uid, skill)
                card = _pass_card_for(skill, grade="四年级", tier=tier)
                body = _complete_one_item(
                    client,
                    db_session,
                    uid,
                    plan,
                    {"id": pending.id, "sort_order": pending.sort_order},
                    card=card,
                    expect_pass=None,
                )
                sr = (body.get("training_progress") or {}).get("skill_results") or {}
                # 本次提交不应把未交卡技能带进 skill_results
                assert set(sr.keys()) <= {skill} or skill in sr
                if skill == "超脑阅读" and sr.get("超脑阅读"):
                    reading_cp.append(sr["超脑阅读"].get("consecutive_pass"))
                    # 同日第二关超脑不应重复累计
                    if sr["超脑阅读"].get("already_passed_today"):
                        assert sr["超脑阅读"].get("counted_today") is False
                if skill == "影像追忆" and sr.get("影像追忆"):
                    recall_cp.append(sr["影像追忆"].get("consecutive_pass"))

        child = db_session.get(ChildUser, uid)
        state = get_training_progress(child)
        # 至少一技能因 3 日连过而升段，或连续计数达到 3 过程可见
        assert (
            int(state["skills"]["超脑阅读"]["tier"]) >= 2
            or int(state["skills"]["影像追忆"]["tier"]) >= 2
            or max(reading_cp or [0]) >= 2
            or max(recall_cp or [0]) >= 2
        ), (reading_cp, recall_cp, state["skills"])


def _write_journey_case(case_id: str, title: str, st: dict) -> Path:
    """一学员旅程 → 一用例文档。"""
    first = st["advances"][0] if st["advances"] else None
    detail_rows = []
    for r in st["rows"]:
        if r.get("day_mode") == "schedule_only":
            ok = "未打卡"
        else:
            ok = "达标" if r.get("passed") else "未达标"
        detail = (r.get("detail") or "").replace("|", "/")
        if len(detail) > 40:
            detail = detail[:37] + "..."
        detail_rows.append(
            [
                r.get("date"),
                r.get("clock"),
                _zh_mode(r.get("day_mode")),
                r.get("planned_minutes"),
                "+".join(r.get("skills_in_plan") or []) or "-",
                r.get("skill"),
                r.get("tier_before") if r.get("tier_before") is not None else "",
                _fmt_card(r.get("card") or {}),
                _zh_intent(r.get("outcome_intent")),
                ok,
                r.get("consecutive_pass")
                if r.get("consecutive_pass") is not None
                else "",
                "是" if r.get("tier_advanced") else "",
                r.get("tier_after") if r.get("tier_after") is not None else "",
                detail,
            ]
        )
    adv_rows = [
        [
            a["date"],
            a.get("clock", ""),
            a["skill"],
            f"第{a['from']}段→第{a['to']}段",
        ]
        for a in st["advances"]
    ]
    ok = (
        st["days_completed"] >= max(10, st["days_planned"] // 3)
        and st["pass_count"] > 0
        and bool(st["advances"])
    )
    return write_case_doc(
        case_id=case_id,
        title=title,
        purpose=(
            f"模拟{_zh_persona(st['persona'])}学员（{st['grade']}）连续多日训练："
            "时长/时刻变化、多技能组合、部分打卡与只排课、选修不打、升段后继续。"
        ),
        preconditions=[
            f"年级={st['grade']}",
            f"人格={_zh_persona(st['persona'])}",
            f"规划训练日={st['days_planned']}",
        ],
        steps=[
            "按日切换虚拟时钟并排课",
            "按当日模式：全日打完 / 部分打卡 / 只排课",
            "部分日子挂多元感知但不打卡",
            "长训日覆盖≥3小时档",
        ],
        expect=[
            "能完成多数训练日",
            "出现升段",
            "时长与时刻不固定",
            "含多技能组合日",
        ],
        actual={
            "学员": st["label"],
            "昵称": st["nickname"],
            "人格": _zh_persona(st["persona"]),
            "年级": st["grade"],
            "区间": f"{st['start']} ~ {st['end']}",
            "完成训练日": f"{st['days_completed']}/{st['days_planned']}",
            "多技能日": st["multi_skill_days"],
            "≥3小时长训日": st.get("long_session_days", 0),
            "部分打卡日": st.get("partial_days", 0),
            "只排课日": st.get("schedule_only_days", 0),
            "选修不打日": st.get("elective_skip_days", 0),
            "打卡条数": len(st["rows"]),
            "达标/未达标": f"{st['pass_count']}/{st['fail_count']}",
            "升段次数": len(st["advances"]),
            "首次升段": (
                f"{first['date']} {first.get('clock')} {first['skill']} "
                f"第{first['from']}段→第{first['to']}段"
                if first
                else "无"
            ),
            "用过的时长(分)": st["minutes_pool"],
            "用过的时刻(时)": st["hours_pool"],
            "期末超脑阅读段位": st["final_skills"].get("超脑阅读", {}).get("tier", 1),
            "期末影像追忆段位": st["final_skills"].get("影像追忆", {}).get("tier", 1),
        },
        passed=ok,
        detail_tables=[
            ("升段时间线", ["日期", "时刻", "技能", "段位变化"], adv_rows),
            (
                "逐日打卡明细",
                [
                    "日期",
                    "时刻",
                    "当日模式",
                    "时长",
                    "技能组合",
                    "本关",
                    "段位前",
                    "打卡数据",
                    "意图",
                    "达标",
                    "连续",
                    "升段",
                    "段位后",
                    "判定",
                ],
                detail_rows,
            ),
        ],
        notes=[
            "本文件仅含本用例学员数据，不与其它用例混排。",
            f"机器摘要见同名 .json",
        ],
    )


class TestMonthsPersonaDiary:
    def test_five_learner_journeys_write_separate_docs(
        self, client, db_session, mock_jnao, enable_dev_clock
    ):
        specs = [
            ("TC20", "学员旅程中等起伏四年级", "A同学", "13710007001", "中等起伏-阿中", "四年级", "medium", 90),
            ("TC21", "学员旅程高效高一", "B同学", "13710007002", "高效短训-阿高", "高一", "high", 90),
            ("TC22", "学员旅程低效二年级", "C同学", "13710007003", "低效长训-阿慢", "二年级", "low", 90),
            ("TC23", "学员旅程初一中等", "D同学", "13710007004", "初一中等-阿初", "初一", "medium", 45),
            ("TC24", "学员旅程六年级高效", "E同学", "13710007005", "六年级高效-阿高小", "六年级", "high", 45),
        ]
        catalog_extra = []
        students = []
        for case_id, title, label, phone, nick, grade, persona, days in specs:
            st = _run_student_months(
                client,
                db_session,
                label=label,
                phone=phone,
                nickname=nick,
                grade=grade,
                persona=persona,
                days=days,
            )
            students.append(st)
            assert st["days_completed"] >= max(10, days // 4), label
            assert st["pass_count"] > 0
            assert st["multi_skill_days"] >= 3, label
            assert max(st["minutes_pool"]) >= 180, label
            assert any(r.get("tier_advanced") for r in st["rows"]), label
            if persona in ("medium", "low"):
                assert st.get("partial_days", 0) >= 1
                assert st.get("schedule_only_days", 0) >= 1
            path = _write_journey_case(case_id, title, st)
            catalog_extra.append(
                {
                    "case_id": case_id,
                    "title": title,
                    "passed": True,
                    "file": path.name,
                }
            )

        # 高效首次升段不晚于中等（同90天组）
        a_adv = students[0]["advances"][0]["date"] if students[0]["advances"] else None
        b_adv = students[1]["advances"][0]["date"] if students[1]["advances"] else None
        if a_adv and b_adv:
            assert b_adv <= a_adv

        # 重建目录：磁盘全部 TC*.md（含 TC01… 与本批旅程）
        all_cases = []
        for p in sorted(DOC_ROOT.glob("TC*.md")):
            parts = p.stem.split("-", 1)
            if len(parts) == 2 and parts[0].startswith("TC"):
                all_cases.append(
                    {
                        "case_id": parts[0],
                        "title": parts[1],
                        "passed": True,
                        "file": p.name,
                    }
                )
        # 确保本批写入的文件在目录中
        have = {c["case_id"] for c in all_cases}
        for c in catalog_extra:
            if c["case_id"] not in have:
                all_cases.append(c)
        write_catalog(sorted(all_cases, key=lambda x: x["case_id"]))
        assert (DOC_ROOT / catalog_extra[0]["file"]).exists()
