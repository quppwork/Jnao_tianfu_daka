"""训练打卡：提交 / 修改 / 历史"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import TrainingItem, TrainingPlan, TrainingRecord
from app.services.training_day import is_plan_globally_cutoff
from app.services.training.checkin_cards import (
    _apply_card_fields_to_record,
    _record_to_dict,
    _sanitize_card,
)
from app.services.training.common import (
    WATCH_COMPLETE_PCT,
    TrainingError,
    _invalidate_after_checkin_change,
    _today_for,
    _user_now,
    invalidate_plan_cache,
)

def submit_checkin(
    db: Session,
    child_user_id: int,
    *,
    plan_id: int,
    item_id: int | None = None,
    ability_type: str | None = None,
    time_spent: str | None = None,
    content: str | None = None,
    result: str | None = None,
    note: str | None = None,
    attitude_pct: int | None = None,
    cards: list[dict] | None = None,
) -> dict:
    plan = db.scalar(
        select(TrainingPlan)
        .options(joinedload(TrainingPlan.items))
        .where(TrainingPlan.id == plan_id)
    )
    if not plan or plan.child_user_id != child_user_id:
        raise TrainingError("训练计划不存在", 404)
    now = _user_now(db, child_user_id)
    if is_plan_globally_cutoff(plan, now=now):
        raise TrainingError("训练日已于凌晨4点截止", 403)

    sorted_items = sorted(plan.items, key=lambda x: x.sort_order)
    from app.services.training_carryover import item_skips_checkin

    # 顺序打卡：必须按 sort_order 完成（选修/免打卡项跳过，不阻塞后续必修打卡）
    target_item = None
    if item_id:
        target_item = db.get(TrainingItem, item_id)
        first_pending = next(
            (it for it in sorted_items if it.checkin_status != "done" and not item_skips_checkin(it)),
            None,
        )
        # 选修项不受顺序限制；必修项必须等前面未打卡的必修项完成
        if (
            first_pending
            and target_item
            and not item_skips_checkin(target_item)
            and target_item.id != first_pending.id
        ):
            raise TrainingError("请按顺序完成训练项")
    else:
        target_item = next(
            (it for it in sorted_items if it.checkin_status != "done" and not item_skips_checkin(it)),
            None,
        )
    if not target_item or target_item.plan_id != plan.id:
        raise TrainingError("训练项不存在", 404)

    # 选修/免打卡项：点开即过关，不设「听完 90%」门槛（见 item_skips_checkin）
    from app.services.training.service import is_item_media_complete
    if not item_skips_checkin(target_item) and not is_item_media_complete(target_item):
        raise TrainingError(
            f"请先听完/看完本项音视频后再打卡（需达到 {int(WATCH_COMPLETE_PCT)}%）",
            403,
        )

    if cards:
        cards = [_sanitize_card(c) for c in cards]

    ability_type, time_spent, content, result, note = _apply_card_fields_to_record(
        cards=cards,
        ability_type=ability_type,
        time_spent=time_spent,
        content=content,
        result=result,
        note=note,
    )

    record = TrainingRecord(
        child_user_id=child_user_id,
        plan_id=plan.id,
        item_id=target_item.id,
        train_date=plan.plan_date,
        ability_type=ability_type,
        time_spent=time_spent,
        content=content,
        result=result,
        note=note,
        attitude_pct=attitude_pct,
        files_json=cards,
    )
    db.add(record)
    # 原子抢占：仅在未打卡时标记 done，防止并发重复提交
    from sqlalchemy import update as sql_update
    claimed = db.execute(
        sql_update(TrainingItem)
        .where(TrainingItem.id == target_item.id, TrainingItem.checkin_status != "done")
        .values(checkin_status="done")
    )
    if claimed.rowcount == 0:
        db.rollback()
        raise TrainingError("该项已完成打卡，请勿重复提交", 409)

    # v2.0: 各技能独立打卡，不再按 block 批量标记完成。
    # pre-v2.0 的 block 批量逻辑已移除。

    from app.services.training_carryover import auto_complete_skipped_checkin_items

    auto_complete_skipped_checkin_items(plan)

    pending = [it for it in plan.items if it.checkin_status != "done"]
    plan.status = "pending" if pending else "completed"

    progress_delta = None
    if cards:
        from app.db.models import ChildUser

        child = db.get(ChildUser, child_user_id)
        from app.services.training.service import _resolve_effective_talent
        talent = _resolve_effective_talent(db, child_user_id)
        talent_code = talent.get("talent_code") if talent else None
        if child and talent_code:
            from app.services.training_mastery import process_checkin_progress
            from app.services.child_training_state import child_grade

            progress_delta = process_checkin_progress(
                db,
                child,
                plan,
                cards,
                talent_code=talent_code,
                grade=child_grade(child),
            )

            # Part 轮换：仅对本次打卡涉及的必修技能计数（一天一次训练前提下按项/卡片计）
            from app.services.training.service import _try_rotate_part_after_checkin
            _try_rotate_part_after_checkin(
                db, child, talent_code, cards=cards, target_item=target_item
            )

    db.commit()
    db.refresh(record)

    # 累计打卡 >= 30 次的新学员 -> 自动转为老学员
    from app.services.training.service import _auto_promote_to_returning
    _auto_promote_to_returning(db, child_user_id)

    # 打卡后清除当日方案缓存，下次 GET /today 拉取最新状态
    invalidate_plan_cache(child_user_id, plan.plan_date)
    _invalidate_after_checkin_change(child_user_id, plan.plan_date)
    out = {"record_id": record.id, "plan_status": plan.status}
    if progress_delta:
        out["training_progress"] = progress_delta
    return out

def get_checkin_record(db: Session, child_user_id: int, record_id: int) -> dict:
    record = db.get(TrainingRecord, record_id)
    if not record or record.child_user_id != child_user_id:
        raise TrainingError("打卡记录不存在", 404)
    plan = db.get(TrainingPlan, record.plan_id) if record.plan_id else None
    return _record_to_dict(record, plan=plan)


def get_today_checkins(db: Session, child_user_id: int, plan_date: date | None = None) -> list[dict]:
    from app.services.training.service import _get_plan_by_date

    plan_date = plan_date or _today_for(db, child_user_id)
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if not plan:
        return []
    rows = db.scalars(
        select(TrainingRecord)
        .where(
            TrainingRecord.child_user_id == child_user_id,
            TrainingRecord.plan_id == plan.id,
        )
        .order_by(TrainingRecord.id.desc())
    ).all()
    return [_record_to_dict(r, plan=plan) for r in rows]


def update_checkin_record(
    db: Session,
    child_user_id: int,
    record_id: int,
    *,
    ability_type: str | None = None,
    time_spent: str | None = None,
    content: str | None = None,
    result: str | None = None,
    note: str | None = None,
    attitude_pct: int | None = None,
    cards: list[dict] | None = None,
) -> dict:
    record = db.get(TrainingRecord, record_id)
    if not record or record.child_user_id != child_user_id:
        raise TrainingError("打卡记录不存在", 404)

    plan = db.get(TrainingPlan, record.plan_id) if record.plan_id else None
    if plan and is_plan_globally_cutoff(plan):
        raise TrainingError("训练日已于凌晨4点截止，无法修改打卡", 403)

    if cards is not None:
        if not cards:
            return delete_checkin_record(db, child_user_id, record_id)
        record.files_json = cards
        auto_ability, auto_time, auto_content, auto_result, auto_note = _apply_card_fields_to_record(
            cards=cards,
            ability_type=ability_type,
            time_spent=time_spent,
            content=content,
            result=result,
            note=note,
        )
        record.ability_type = auto_ability
        record.time_spent = auto_time
        record.content = auto_content
        record.result = auto_result
        record.note = auto_note
    else:
        if ability_type is not None:
            record.ability_type = ability_type
        if content is not None:
            record.content = content

    if time_spent is not None and cards is None:
        record.time_spent = time_spent
    if result is not None and cards is None:
        record.result = result
    if note is not None and cards is None:
        record.note = note
    if attitude_pct is not None:
        record.attitude_pct = attitude_pct

    plan = db.get(TrainingPlan, record.plan_id) if record.plan_id else None
    from app.services.training.service import (
        _resolve_effective_talent,
        _sync_plan_after_record_change,
    )

    plan_status = _sync_plan_after_record_change(db, plan)
    progress_delta = None
    if plan and cards is not None:
        from app.db.models import ChildUser
        from app.services.training_mastery import process_checkin_progress

        child = db.get(ChildUser, child_user_id)
        talent = _resolve_effective_talent(db, child_user_id)
        talent_code = talent.get("talent_code") if talent else None
        if child and talent_code:
            db.flush()
            from app.services.child_training_state import child_grade

            progress_delta = process_checkin_progress(
                db,
                child,
                plan,
                [],
                talent_code=talent_code,
                grade=child_grade(child),
            )
    db.commit()
    db.refresh(record)
    if plan:
        _invalidate_after_checkin_change(child_user_id, plan.plan_date)
    out = {"record": _record_to_dict(record, plan=plan), "plan_status": plan_status}
    if progress_delta:
        out["training_progress"] = progress_delta
    return out


def delete_checkin_record(db: Session, child_user_id: int, record_id: int) -> dict:
    record = db.get(TrainingRecord, record_id)
    if not record or record.child_user_id != child_user_id:
        raise TrainingError("打卡记录不存在", 404)

    plan = db.get(TrainingPlan, record.plan_id) if record.plan_id else None
    if plan and is_plan_globally_cutoff(plan):
        raise TrainingError("训练日已于凌晨4点截止，无法修改打卡", 403)
    db.delete(record)
    db.flush()
    from app.services.training.service import (
        _resolve_effective_talent,
        _sync_plan_after_record_change,
    )

    plan_status = _sync_plan_after_record_change(db, plan, deleted_record=record)
    progress_delta = None
    if plan:
        from app.db.models import ChildUser
        from app.services.training_mastery import process_checkin_progress

        child = db.get(ChildUser, child_user_id)
        talent = _resolve_effective_talent(db, child_user_id)
        talent_code = talent.get("talent_code") if talent else None
        if child and talent_code:
            from app.services.child_training_state import child_grade

            progress_delta = process_checkin_progress(
                db,
                child,
                plan,
                [],
                talent_code=talent_code,
                grade=child_grade(child),
            )
    db.commit()
    if plan:
        _invalidate_after_checkin_change(child_user_id, plan.plan_date)
    out = {"deleted": True, "plan_status": plan_status}
    if progress_delta:
        out["training_progress"] = progress_delta
    return out

def get_checkin_history(
    db: Session,
    child_user_id: int,
    limit: int = 60,
    *,
    exclude_today: bool = False,
) -> list[dict]:
    fetch_limit = min(limit * 5, 500) if exclude_today else limit
    rows = db.scalars(
        select(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
        .order_by(TrainingRecord.created_at.desc(), TrainingRecord.id.desc())
        .limit(fetch_limit)
    ).all()
    plan_ids = {r.plan_id for r in rows if r.plan_id}
    plans: dict[int, TrainingPlan] = {}
    if plan_ids:
        for plan in db.scalars(select(TrainingPlan).where(TrainingPlan.id.in_(plan_ids))).all():
            plans[plan.id] = plan
    changed = False
    for rec in rows:
        if not rec.train_date and rec.plan_id and plans.get(rec.plan_id):
            rec.train_date = plans[rec.plan_id].plan_date
            changed = True
        elif not rec.train_date and rec.created_at:
            rec.train_date = rec.created_at.date()
            changed = True
    if changed:
        db.commit()

    items = [_record_to_dict(r, plan=plans.get(r.plan_id) if r.plan_id else None) for r in rows]

    if exclude_today:
        today = _today_for(db, child_user_id)
        from app.services.training.service import _get_plan_by_date
        today_plan = _get_plan_by_date(db, child_user_id, today)

        def _is_active_today_record(item: dict) -> bool:
            pid = item.get("plan_id")
            plan = plans.get(pid) if pid else None
            if today_plan and pid == today_plan.id:
                return True
            if plan and plan.plan_date == today:
                return True
            train_date = item.get("train_date")
            if train_date == today.isoformat():
                return True
            return False

        items = [item for item in items if not _is_active_today_record(item)]

    return items[:limit]

