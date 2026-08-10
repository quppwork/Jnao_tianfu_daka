"""排课 Agent 编排 — 原生 function-calling 工具循环。

禁止 import Guide / QA runner。只出技能草案，不写 DB。
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.agents.training_schedule.persona import SYSTEM_PROMPT
from app.agents.training_schedule.tools import (
    call_tool,
    list_tools,
    openai_tool_schemas,
    tool_result_text,
)
from app.agents.training_schedule.tools._ctx import (
    ScheduleRequestCtx,
    clear_request_ctx,
    set_request_ctx,
)
from app.core.logger import get_logger
from app.services.training_formula_engine import HistoryEntry, expand_formula
from app.agents.training_schedule.tools.curriculum_map import (
    build_curriculum_overview,
    build_skill_availability,
    required_slot_count,
)

logger = get_logger("training_schedule.runner")

MAX_TOOL_ROUNDS = 4
MAX_TOOLS_TOTAL = 8
MAX_TOOLS_PER_TURN = 3
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


class ScheduleAssistError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}" if message else code)


def _build_request_ctx(
    db: Session,
    child_user_id: int,
    planned_minutes: int,
    *,
    plan_date: date | None,
) -> ScheduleRequestCtx:
    from app.db.models import ChildUser
    from app.services.assessment_service import resolve_effective_talent
    from app.services.child_training_state import (
        child_grade,
        filter_active_skills,
        get_skills_with_records,
        get_training_progress,
        overall_tier,
    )
    from app.services.training_mastery import _grade_band
    from app.services.training_schedule_service import _collect_schedule_history

    talent = resolve_effective_talent(db, child_user_id) or {}
    child = db.get(ChildUser, child_user_id)
    state = get_training_progress(child) if child else {}
    skills_with_records = get_skills_with_records(db, child_user_id)
    active_state = filter_active_skills(state, skills_with_records)
    o_tier = overall_tier(active_state)
    grade = child_grade(child) if child else ""
    grade_band = _grade_band(grade) or "primary_low"
    skill_tiers: dict[str, int] = {}
    for skill_name, skill_info in (state.get("skills") or {}).items():
        if isinstance(skill_info, dict) and "tier" in skill_info:
            skill_tiers[skill_name] = int(skill_info["tier"])
    history = _collect_schedule_history(db, child_user_id, plan_date)
    avail = build_skill_availability(overall_tier=o_tier)
    available = list(avail.get("selectable_now") or [])
    rule = expand_formula(
        planned_minutes,
        overall_tier=o_tier,
        grade_band=grade_band,
        skill_tiers=skill_tiers,
        history=history,
    )
    rule_slots = list(rule.get("slots") or [])
    target_n = required_slot_count(rule_slots)
    return ScheduleRequestCtx(
        planned_minutes=planned_minutes,
        plan_date=plan_date,
        overall_tier=o_tier,
        grade=grade or "",
        grade_band=grade_band,
        skill_tiers=skill_tiers,
        history=history,
        talent_tag=talent.get("talent_tag"),
        talent_code=talent.get("talent_code"),
        training_days=int(state.get("training_days") or 0),
        available_skills=available,
        rule_slots=rule_slots,
        rule_strategy=rule.get("strategy"),
        target_slot_count=target_n,
    )


def _build_pad_priority(
    *,
    available: list[str],
    key_skills: list[str],
    secondary_skills: list[str],
    struggling: list[str],
    stable: list[str],
) -> list[str]:
    """投影补齐顺序：弱项 → 本阶重点 → 次重点 → 其余可排（排除过稳可后置但仍可补）。"""
    avail_set = set(available)
    out: list[str] = []
    seen: set[str] = set()

    def _add(names: list[str]) -> None:
        for n in names:
            if n in avail_set and n not in seen:
                out.append(n)
                seen.add(n)

    _add(list(struggling or []))
    # 弱项可多占一轮：再追加一遍 struggling（允许重复占槽）
    for n in struggling or []:
        if n in avail_set:
            out.append(n)
    _add(list(key_skills or []))
    _add(list(secondary_skills or []))
    _add([s for s in available if s not in set(stable or [])])
    _add(list(available))
    return out


def _bootstrap_user_message(req: ScheduleRequestCtx, db: Session, child_user_id: int) -> str:
    """首轮注入：课表 + 画像 + 软预算；不注入规则引擎草案名单。"""
    from app.agents.training_schedule.tools.checkin_summary import (
        build_checkin_skill_summary,
        build_rhythm_summary,
    )

    overview = build_curriculum_overview(overall_tier=req.overall_tier)
    avail = build_skill_availability(overall_tier=req.overall_tier)
    tiers_brief = {
        k: {
            "key": v.get("key_skills"),
            "secondary": v.get("secondary_skills"),
            "weights": v.get("weights"),
        }
        for k, v in (overview.get("tiers") or {}).items()
    }
    recent: list[str] = []
    for h in req.history[-7:]:
        for sk in h.skills or ():
            if sk and sk not in recent:
                recent.append(sk)

    checkin = build_checkin_skill_summary(
        db,
        child_user_id,
        days=14,
        skill_tiers=req.skill_tiers,
        grade_band=req.grade_band,
    )
    rhythm = build_rhythm_summary(db, child_user_id, lookback_days=14)

    focus = overview.get("current_tier_focus") or {}
    selectable = list(avail.get("selectable_now") or req.available_skills)
    req.pad_priority = _build_pad_priority(
        available=selectable,
        key_skills=list(focus.get("key_skills") or []),
        secondary_skills=list(focus.get("secondary_skills") or []),
        struggling=list(checkin.get("struggling_skills") or []),
        stable=list(checkin.get("stable_skills") or []),
    )

    checkin_brief = {
        "days": checkin.get("days"),
        "struggling_skills": checkin.get("struggling_skills"),
        "stable_skills": checkin.get("stable_skills"),
        "skills": (checkin.get("skills") or [])[:12],
        "hint": checkin.get("hint"),
    }
    rhythm_brief = {
        "checkin_streak_days": rhythm.get("checkin_streak_days"),
        "days_since_last_checkin": rhythm.get("days_since_last_checkin"),
        "avg_completion_ratio": rhythm.get("avg_completion_ratio"),
        "recent_plan_completion": (rhythm.get("recent_plan_completion") or [])[:7],
        "hint": rhythm.get("hint"),
    }

    budget = req.target_slot_count
    payload = {
        "task": f"安排今日 {req.planned_minutes} 分钟训练",
        "slot_budget": budget,
        "student": {
            "overall_tier": req.overall_tier,
            "grade": req.grade,
            "grade_band": req.grade_band,
            "talent_tag": req.talent_tag,
            "training_days": req.training_days,
            "skill_tiers": req.skill_tiers,
            "recent_skills": recent,
        },
        "selectable_now": selectable,
        "importance_now": avail.get("importance_now"),
        "locked_preview": avail.get("locked_preview"),
        "curriculum_tiers_brief": tiers_brief,
        "grade_notes": overview.get("grade_notes"),
        "checkin_quality": checkin_brief,
        "training_rhythm": rhythm_brief,
        "instruction": (
            "请按学生画像自主决定必修技能顺序（可重复弱项）；"
            f"skills 长度建议约 {budget} 项（时长档软预算，非必须抄满某一标准名单）；"
            "只能从 selectable_now 选题；优先 struggling 与 importance_now.key；"
            "勿模仿规则/标准方案名单；然后调用 propose_skill_draft。"
        ),
    }
    return json.dumps(payload, ensure_ascii=False)


def _parse_tool_calls(message: dict | None) -> list[dict[str, Any]]:
    if not isinstance(message, dict):
        return []
    raw_calls = message.get("tool_calls")
    if not isinstance(raw_calls, list):
        fc = message.get("function_call")
        if isinstance(fc, dict) and fc.get("name"):
            raw_calls = [{"type": "function", "function": fc, "id": "call_0"}]
        else:
            return []
    allowed = {s["function"]["name"] for s in openai_tool_schemas()}
    out: list[dict[str, Any]] = []
    for i, call in enumerate(raw_calls):
        if not isinstance(call, dict):
            continue
        fn = call.get("function") if isinstance(call.get("function"), dict) else call
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        if name not in allowed:
            continue
        args_raw = fn.get("arguments", {})
        args: dict[str, Any] = {}
        if isinstance(args_raw, dict):
            args = args_raw
        elif isinstance(args_raw, str) and args_raw.strip():
            try:
                parsed = json.loads(args_raw)
                if isinstance(parsed, dict):
                    args = parsed
            except json.JSONDecodeError:
                args = {}
        call_id = call.get("id") or f"call_{i}"
        out.append({"id": call_id, "name": str(name), "args": args})
        if len(out) >= MAX_TOOLS_PER_TURN:
            break
    return out


def _parse_content_draft(content: str | None) -> tuple[list[str] | None, str | None]:
    """从模型自由文本中解析 skills + 可选 reason。"""
    if not content or not str(content).strip():
        return None, None
    text = str(content).strip()
    m = _JSON_FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    if not text.startswith(("{", "[")):
        brace = text.find("{")
        brack = text.find("[")
        starts = [i for i in (brace, brack) if i >= 0]
        if not starts:
            return None, None
        text = text[min(starts) :]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, None
    skills: list[str] = []
    items = data
    reason: str | None = None
    if isinstance(data, dict):
        items = data.get("skills") or data.get("items") or data.get("slots") or []
        raw_reason = data.get("reason")
        if raw_reason is not None:
            reason = str(raw_reason).strip() or None
            if reason and len(reason) > 500:
                reason = reason[:500]
    if not isinstance(items, list):
        return None, reason
    for it in items:
        if isinstance(it, str) and it.strip():
            skills.append(it.strip())
        elif isinstance(it, dict) and it.get("skill"):
            skills.append(str(it["skill"]).strip())
    return (skills or None), reason


async def run_schedule_assist(
    db: Session,
    child_user_id: int,
    planned_minutes: int,
    *,
    plan_date: date | None = None,
    timeout_sec: float = 10.0,
) -> dict[str, Any]:
    """工具循环 → 技能草案。成功返回 dict；失败抛 ScheduleAssistError。"""
    from app.services.doubao_client import chat_completion_message, is_configured

    if not is_configured():
        raise ScheduleAssistError("llm_none", "豆包未配置")

    list_tools()
    req = _build_request_ctx(db, child_user_id, planned_minutes, plan_date=plan_date)
    if not req.available_skills:
        raise ScheduleAssistError("no_available", "当前 Tier 无可用技能")
    if not req.rule_slots:
        raise ScheduleAssistError("empty_rule", "规则引擎无槽位")

    set_request_ctx(req)
    audit: list[dict[str, Any]] = []
    try:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _bootstrap_user_message(req, db, child_user_id),
            },
        ]
        tools = openai_tool_schemas()
        deadline = asyncio.get_event_loop().time() + max(3.0, timeout_sec)
        # 首轮已注入全课表+N+重点；默认可直接 propose，也可先补查再提交
        ready_to_propose = True

        for round_i in range(MAX_TOOL_ROUNDS):
            if req.draft_submitted:
                break
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0.5:
                raise ScheduleAssistError("timeout", f"超时 {timeout_sec}s")

            used_names = {a["name"] for a in audit}
            # 第一轮允许 auto 补查；之后或已查过 available/curriculum 则强制 propose
            if round_i == 0 and not used_names:
                tool_choice: str | dict = "auto"
            elif ready_to_propose or "get_available_skills" in used_names or "get_curriculum_overview" in used_names:
                tool_choice = {
                    "type": "function",
                    "function": {"name": "propose_skill_draft"},
                }
            else:
                tool_choice = "auto"

            # 单轮可用剩余总预算（上限即 TRAINING_AGENT_SCHEDULE_TIMEOUT，默认 600s）
            round_timeout = max(3.0, min(remaining, timeout_sec))
            logger.info(
                "training_schedule llm uid=%s round=%s remaining=%.1f tool_choice=%s N=%s",
                child_user_id,
                round_i,
                remaining,
                tool_choice if isinstance(tool_choice, str) else "propose_skill_draft",
                req.target_slot_count,
            )
            msg = await chat_completion_message(
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=500,
                timeout=round_timeout,
            )
            if msg is None:
                raise ScheduleAssistError("llm_none", "豆包无响应")

            calls = _parse_tool_calls(msg)
            content = msg.get("content") if isinstance(msg.get("content"), str) else ""

            if not calls:
                # 兜底：模型直接吐 JSON
                draft, parsed_reason = _parse_content_draft(content)
                if draft:
                    req.draft_skills = [s for s in draft if s in set(req.available_skills)]
                    if req.draft_skills:
                        req.draft_reason = parsed_reason
                        req.draft_submitted = True
                        audit.append({
                            "round": round_i,
                            "name": "_content_draft",
                            "ok": True,
                        })
                        break
                raise ScheduleAssistError(
                    "no_tool_calls",
                    "模型未调用工具且无法解析草案",
                )

            # 追加 assistant（含 tool_calls）
            messages.append({
                "role": "assistant",
                "content": content or None,
                "tool_calls": msg.get("tool_calls") or [
                    {
                        "id": c["id"],
                        "type": "function",
                        "function": {
                            "name": c["name"],
                            "arguments": json.dumps(c["args"], ensure_ascii=False),
                        },
                    }
                    for c in calls
                ],
            })

            for call in calls:
                if len(audit) >= MAX_TOOLS_TOTAL:
                    break
                name = call["name"]
                args = call["args"]
                try:
                    result = call_tool(db, child_user_id, name, args)
                    ok = True
                    err = None
                except Exception as e:
                    result = {"error": str(e)}
                    ok = False
                    err = str(e)
                audit.append({
                    "round": round_i,
                    "name": name,
                    "args": args,
                    "ok": ok,
                    "error": err,
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": tool_result_text(name, result),
                })
                logger.info(
                    "training_schedule tool uid=%s round=%s name=%s ok=%s",
                    child_user_id,
                    round_i,
                    name,
                    ok,
                )
                if name in ("get_available_skills", "get_curriculum_overview") and ok:
                    ready_to_propose = True
                if req.draft_submitted:
                    break

            if req.draft_submitted:
                break

            # 首轮若只做了只读补查，下一轮强制提交
            if round_i == 0 and not req.draft_submitted:
                ready_to_propose = True
                messages.append({
                    "role": "user",
                    "content": (
                        f"信息已足够。请立即调用 propose_skill_draft，"
                        f"skills 长度建议约 {req.target_slot_count}，且只能用 selectable_now；"
                        f"按画像自主排序（可重复弱项），勿抄标准方案；同时传 reason。"
                    ),
                })
            elif ready_to_propose and not req.draft_submitted:
                messages.append({
                    "role": "user",
                    "content": (
                        f"请立即调用 propose_skill_draft，传入约 {req.target_slot_count} 个 skills，"
                        f"并填写 reason（按画像，勿抄标准方案）。"
                    ),
                })

        if not req.draft_submitted or not req.draft_skills:
            raise ScheduleAssistError("no_draft", "未提交技能草案")

        return {
            "draft": list(req.draft_skills),
            "reason": req.draft_reason,
            "available_skills": list(req.available_skills),
            "pad_priority": list(req.pad_priority),
            "rule_slots": list(req.rule_slots),
            "rule_strategy": req.rule_strategy,
            "overall_tier": req.overall_tier,
            "grade_band": req.grade_band,
            "target_slot_count": req.target_slot_count,
            "tools_used": audit,
        }
    finally:
        clear_request_ctx()
