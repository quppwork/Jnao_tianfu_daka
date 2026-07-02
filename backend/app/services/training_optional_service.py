"""可选训练项 — 按天赋权重推荐，孩子确认后再加入今日方案"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload, Session

from app.db.models import ChildUser, ContentItem, TrainingItem, TrainingPlan
from app.services.assessment_service import resolve_effective_talent
from app.services.child_training_state import get_skill_oss_position, get_training_progress
from app.services.content_meta import content_display_title, estimate_duration_min, item_instruction, parse_item_meta
from app.services.talent_content_pool import get_talent_content_pool
from app.services.training_catalog_sync import repair_plan_media_items
from app.services.training_child_guide import build_coach_text_for_plan
# v2.0: _optional_ranked inlined from deleted training_duration_pack
def _optional_ranked(line_spec: dict, talent_primary: str | None) -> list[dict]:
    ranked = []
    for opt in line_spec.get("optional") or []:
        if not isinstance(opt, dict) or not opt.get("skill"):
            continue
        weights = opt.get("weight_by_talent") or {}
        w = float(weights.get(talent_primary or "") or 0)
        if w <= 0:
            w = 0.25
        ranked.append({"skill": opt["skill"], "weight": w, "push_empty_placeholder": bool(opt.get("push_empty_placeholder")), "content_type": opt.get("content_type") or "audio"})
    ranked.sort(key=lambda x: -x["weight"])
    return ranked
from app.services.training_service import TrainingError, _get_plan_by_date, _plan_to_response
from app.services.training_day import get_training_day
from config.loader import load_training_curriculum

OPTIONAL_DAILY_KEY = "training_optional_daily"


def _optional_daily(child: ChildUser, plan_date: date) -> dict:
    pj = child.profile_json if isinstance(child.profile_json, dict) else {}
    raw = pj.get(OPTIONAL_DAILY_KEY)
    if not isinstance(raw, dict) or raw.get("date") != plan_date.isoformat():
        return {"date": plan_date.isoformat(), "declined": []}
    declined = raw.get("declined") or []
    return {"date": plan_date.isoformat(), "declined": list(declined)}


def _save_optional_daily(db: Session, child: ChildUser, plan_date: date, declined: list[str]) -> None:
    pj = dict(child.profile_json or {})
    pj[OPTIONAL_DAILY_KEY] = {
        "date": plan_date.isoformat(),
        "declined": declined,
    }
    child.profile_json = pj
    db.flush()


def _skills_in_plan(plan: TrainingPlan) -> set[str]:
    skills: set[str] = set()
    for item in plan.items:
        if item.instructions and str(item.instructions).strip().startswith("{"):
            try:
                import json

                meta = json.loads(item.instructions)
                if meta.get("skill"):
                    skills.add(meta["skill"])
            except Exception:
                pass
        title = (item.title or "")
        for name in ("高效作业", "开口窍", "感知力"):
            if name in title:
                skills.add(name)
    return skills


def _block_for_slot(slot: int) -> str:
    if slot == 1:
        return "A"
    if slot == 2:
        return "B"
    return f"T{slot}"


def _max_training_slot(plan: TrainingPlan) -> int:
    max_slot = 0
    for item in plan.items:
        if not item.instructions:
            continue
        try:
            import json

            meta = json.loads(item.instructions)
            block = meta.get("block") or "A"
            if block == "A":
                max_slot = max(max_slot, 1)
            elif block == "B":
                max_slot = max(max_slot, 2)
            elif block.startswith("T") and block[1:].isdigit():
                max_slot = max(max_slot, int(block[1:]))
        except Exception:
            pass
    return max_slot


def _merge_offer_status(
    offers: list[dict],
    plan: TrainingPlan,
    declined: list[str],
) -> list[dict]:
    in_plan = _skills_in_plan(plan)
    out: list[dict] = []
    for offer in offers:
        skill = offer["skill"]
        status = "pending"
        if skill in in_plan:
            status = "accepted"
        elif skill in declined:
            status = "declined"
        merged = dict(offer)
        merged["status"] = status
        out.append(merged)
    return out


def get_optional_offers_for_child(
    db: Session,
    child_user_id: int,
    plan: TrainingPlan,
) -> list[dict]:
    """v2.0: 选修由 formula_engine + elective_service 管理，此处返回空"""
    return []


def _add_optional_plan_row(
    db: Session,
    plan: TrainingPlan,
    skill: str,
    *,
    talent_code: int,
    state: dict,
    training_slot: int,
) -> TrainingItem:
    pool = get_talent_content_pool(db, talent_code)
    line_key = state.get("main_line") or "A"
    line = (load_training_curriculum().get("main_lines") or {}).get(line_key) or {}
    ranked = _optional_ranked(line, None)
    force_ph = skill == "开口窍"
    for o in ranked:
        if o["skill"] == skill:
            force_ph = o["push_empty_placeholder"] or o["content_type"] == "video"
            break

    block = _block_for_slot(training_slot)
    role = "optional"
    rows: list[dict] = []
    _append_single_skill(
        rows,
        pool,
        state,
        skill,
        training_slot=training_slot,
        role=role,
        rounds=1,
        force_placeholder=force_ph,
    )
    if not rows:
        raise TrainingError(f"无法生成可选训练「{skill}」", 400)

    row = rows[0]
    sort_order = max((it.sort_order for it in plan.items), default=0) + 1

    ph = row.get("placeholder_skill")
    if ph:
        title = (
            f"{ph}（占位）"
            if ph == "开口窍"
            else "多元感知（待同步）"
            if ph == "感知力"
            else f"{ph}（待同步）"
        )
        ability = "perception" if ph == "感知力" else "placeholder"
        inst_type = "perception" if ph == "感知力" else "placeholder"
        item = TrainingItem(
            plan_id=plan.id,
            sort_order=sort_order,
            ability_type=ability,
            title=title,
            duration_min=0,
            instructions=item_instruction(block, inst_type),
            checkin_status="pending",
        )
        db.add(item)
        db.flush()
        return item

    cid = row.get("content_item_id")
    content = db.get(ContentItem, cid) if cid else None
    if not content:
        raise TrainingError(f"可选训练「{skill}」内容不存在", 503)

    meta = parse_item_meta(content)
    resolved_type = row.get("item_type") or meta.get("content_type") or "audio"
    inst = item_instruction(block, resolved_type)
    try:
        payload = __import__("json").loads(inst)
        payload["skill"] = meta.get("skill") or skill
        payload["role"] = role
        inst = __import__("json").dumps(payload, ensure_ascii=False)
    except Exception:
        pass

    title = content_display_title(content)
    item = TrainingItem(
        plan_id=plan.id,
        sort_order=sort_order,
        ability_type="perception" if resolved_type == "perception" else "audio",
        title=title,
        duration_min=estimate_duration_min(content),
        audio_url=content.play_url,
        video_url=content.video_url,
        content_item_id=content.id,
        instructions=inst,
        checkin_status="pending",
    )
    db.add(item)
    db.flush()
    return item


def accept_optional_training(
    db: Session,
    child_user_id: int,
    skill: str,
    *,
    plan_date: date | None = None,
) -> dict:
    plan_date = plan_date or get_training_day()
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if not plan:
        raise TrainingError("训练计划不存在", 404)
    if plan.status == "completed":
        raise TrainingError("今日训练已完成", 403)

    child = db.get(ChildUser, child_user_id)
    if not child:
        raise TrainingError("学员不存在", 404)

    offers = get_optional_offers_for_child(db, child_user_id, plan)
    offer = next((o for o in offers if o["skill"] == skill), None)
    if not offer:
        raise TrainingError(f"今日无可选训练「{skill}」", 400)
    if offer["status"] == "accepted":
        db.commit()
        plan = _get_plan_by_date(db, child_user_id, plan_date)
        return _plan_to_response(plan, db=db)
    if offer["status"] == "declined":
        daily = _optional_daily(child, plan_date)
        declined = [s for s in daily.get("declined") or [] if s != skill]
        _save_optional_daily(db, child, plan_date, declined)

    if skill in _skills_in_plan(plan):
        db.commit()
        plan = _get_plan_by_date(db, child_user_id, plan_date)
        return _plan_to_response(plan, db=db)

    eff = resolve_effective_talent(db, child_user_id)
    talent_code = eff.get("talent_code") if eff else None
    if not talent_code:
        raise TrainingError("请先完成天赋测评或选择天赋", 403)
    state = get_training_progress(child)
    next_slot = _max_training_slot(plan) + 1

    _add_optional_plan_row(
        db,
        plan,
        skill,
        talent_code=talent_code,
        state=state,
        training_slot=next_slot,
    )
    repair_plan_media_items(db, plan, talent_code)
    plan.report_text = build_coach_text_for_plan(plan)
    db.commit()
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    return _plan_to_response(plan, db=db)


def decline_optional_training(
    db: Session,
    child_user_id: int,
    skill: str,
    *,
    plan_date: date | None = None,
) -> dict:
    plan_date = plan_date or get_training_day()
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if not plan:
        raise TrainingError("训练计划不存在", 404)

    child = db.get(ChildUser, child_user_id)
    if not child:
        raise TrainingError("学员不存在", 404)

    offers = get_optional_offers_for_child(db, child_user_id, plan)
    if not any(o["skill"] == skill for o in offers):
        raise TrainingError(f"今日无可选训练「{skill}」", 400)

    daily = _optional_daily(child, plan_date)
    declined = list(daily.get("declined") or [])
    if skill not in declined:
        declined.append(skill)
    _save_optional_daily(db, child, plan_date, declined)
    db.commit()
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    resp = _plan_to_response(plan, db=db)
    resp["optional_offers"] = get_optional_offers_for_child(db, child_user_id, plan)
    return resp
