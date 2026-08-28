"""训练选修：增删、开关、整表替换技能"""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ContentItem, TrainingItem, TrainingPlan, TrainingRecord
from app.services.content_meta import parse_item_instruction
from app.services.training.common import TrainingError, invalidate_plan_cache
from app.services.training_day import is_plan_globally_cutoff

def toggle_elective_item(
    db: Session,
    child_user_id: int,
    plan_id: int,
    skill: str,
    action: str,
) -> dict:
    """统一开关选修项：action="add" 插到方案最前，action="remove" 按技能名移除"""
    if action == "add":
        return append_elective_item(db, child_user_id, plan_id, skill)
    elif action == "remove":
        # 按技能名查找 plan 中的选修项
        plan = db.get(TrainingPlan, plan_id)
        if not plan or plan.child_user_id != child_user_id:
            raise TrainingError("训练计划不存在", 404)
        target = None
        for item in plan.items:
            inst = parse_item_instruction(
                item.instructions if item.instructions and str(item.instructions).strip().startswith("{") else None
            )
            if inst.get("skill") == skill:
                target = item
                break
            title = (item.title or "").strip()
            if title == skill or title == f"{skill}（待同步）":
                target = item
                break
        if not target:
            raise TrainingError(f"方案中未找到选修项「{skill}」", 404)
        return remove_plan_item(db, child_user_id, target.id)
    raise TrainingError("action 必须为 add 或 remove", 400)

def _resort_plan_elective_priority(plan) -> None:
    """重排方案 sort_order：选修项按固定优先级排最前，必修项保持原相对顺序。"""
    items = sorted(plan.items, key=lambda x: x.sort_order or 0)

    def sort_key(it):
        inst = parse_item_instruction(
            it.instructions
            if it.instructions and str(it.instructions).strip().startswith("{")
            else None
        )
        skill = inst.get("skill") if inst else None
        if skill in ELECTIVE_PRIORITY:
            return (0, ELECTIVE_PRIORITY[skill])
        return (1, 0)

    for i, it in enumerate(sorted(items, key=sort_key), start=1):
        it.sort_order = i


def append_elective_item(
    db: Session,
    child_user_id: int,
    plan_id: int,
    skill: str,
) -> dict:
    """在现有方案最前面插入一个选修训练项（如多元感知），有 OSS 音频则带音频"""
    from app.services.content_meta import (
        content_display_title, estimate_duration_min, parse_item_meta,
    )
    from app.services.talent_content_pool import get_talent_content_pool
    from app.services.assessment_service import resolve_effective_talent
    from app.services.training_catalog_sync import ensure_supplementary_catalogs, repair_plan_media_items
    from app.services.training_schedule_service import _attach_videos_to_items
    from app.services.training_child_guide import build_coach_text_for_plan

    plan = db.get(TrainingPlan, plan_id)
    if not plan or plan.child_user_id != child_user_id:
        raise TrainingError("训练计划不存在", 404)
    if is_plan_globally_cutoff(plan):
        raise TrainingError("训练日已于凌晨4点截止", 403)

    # 去重：同一技能已在方案中则跳过（含无 content_item_id 的占位项）
    search_skill = "感知力" if skill == "多元感知" else skill
    for existing in plan.items:
        inst = parse_item_instruction(
            existing.instructions
            if existing.instructions and str(existing.instructions).strip().startswith("{")
            else None
        )
        if inst.get("skill") == skill:
            db.commit()
            from app.services.training.service import _get_plan_by_date, _plan_to_response
            plan = _get_plan_by_date(db, child_user_id, plan.plan_date)
            return _plan_to_response(plan, db=db)
        if existing.content_item_id:
            ci = db.get(ContentItem, existing.content_item_id)
            if ci:
                from app.services.content_meta import parse_item_meta as _pim
                if _pim(ci).get("skill") == search_skill:
                    db.commit()
                    from app.services.training.service import _get_plan_by_date, _plan_to_response
                    plan = _get_plan_by_date(db, child_user_id, plan.plan_date)
                    return _plan_to_response(plan, db=db)

    items = sorted(plan.items, key=lambda x: x.sort_order)
    # 选修项插到最前面：取当前最小 sort_order 再减 1（负值排序正常）
    next_sort = (items[0].sort_order - 1) if items else 1

    talent = resolve_effective_talent(db, child_user_id)
    talent_code = talent.get("talent_code") if talent else None
    pool = get_talent_content_pool(db, talent_code) if talent_code else []

    content = None
    for item in pool:
        meta = parse_item_meta(item)
        if meta.get("skill") == search_skill:
            content = item
            break

    # fallback: talent pool 未命中时，查 content_item 全表（视频等跨天赋内容）
    if not content:
        content = db.scalar(
            select(ContentItem).where(
                ContentItem.status == 1,
                ContentItem.instructions.contains(search_skill),
            ).limit(1)
        )

    if content:
        is_video = (content.content_type == "video")
        inst_data = {"skill": skill, "item_type": "elective", "blocks_next": False}
        if is_video:
            inst_data["content_type"] = "video"
        inst = json.dumps(inst_data, ensure_ascii=False)
        db.add(TrainingItem(
            plan_id=plan.id, sort_order=next_sort, ability_type="elective",
            title=content_display_title(content),
            duration_min=estimate_duration_min(content),
            audio_url=None if is_video else content.play_url,
            video_url=content.play_url if is_video else content.video_url,
            content_item_id=content.id, instructions=inst,
            checkin_status="pending",
        ))
    else:
        db.add(TrainingItem(
            plan_id=plan.id, sort_order=next_sort, ability_type="elective",
            title=f"{skill}（待同步）", duration_min=0,
            instructions=json.dumps(
                {"skill": skill, "item_type": "elective", "blocks_next": False},
                ensure_ascii=False,
            ),
            checkin_status="pending",
        ))

    db.flush()  # 确保新项进入 plan.items，再按固定优先级重排
    _resort_plan_elective_priority(plan)

    if talent_code:
        ensure_supplementary_catalogs(db)
        repair_plan_media_items(db, plan, talent_code)
    else:
        _attach_videos_to_items(db, plan)
    plan.report_text = build_coach_text_for_plan(plan)
    db.commit()
    invalidate_plan_cache(child_user_id, plan.plan_date)
    from app.core.cache import invalidate_user_training
    invalidate_user_training(child_user_id, plan_date=plan.plan_date)

    from app.services.training.service import _get_plan_by_date, _plan_to_response
    plan = _get_plan_by_date(db, child_user_id, plan.plan_date)
    return _plan_to_response(plan, db=db)


def remove_plan_item(
    db: Session,
    child_user_id: int,
    item_id: int,
) -> dict:
    """从方案中移除一个训练项（仅限选修项）"""
    item = db.get(TrainingItem, item_id)
    if not item:
        raise TrainingError("训练项不存在", 404)
    plan = db.get(TrainingPlan, item.plan_id)
    if not plan or plan.child_user_id != child_user_id:
        raise TrainingError("训练项不存在", 404)
    if is_plan_globally_cutoff(plan):
        raise TrainingError("训练日已于凌晨4点截止", 403)

    # 仅允许移除选修项
    from app.services.training_carryover import item_skips_checkin
    if not item_skips_checkin(item):
        raise TrainingError("只能移除选修训练项", 403)

    from sqlalchemy import update

    db.execute(update(TrainingRecord).where(TrainingRecord.item_id == item_id).values(item_id=None))
    db.delete(item)
    db.flush()  # 确保被删项从 plan.items 中移除
    # 重排剩余项的 sort_order
    remaining = sorted(plan.items, key=lambda x: x.sort_order or 0)
    for i, it in enumerate(remaining, start=1):
        it.sort_order = i

    from app.services.training_child_guide import build_coach_text_for_plan
    plan.report_text = build_coach_text_for_plan(plan)
    db.commit()
    invalidate_plan_cache(child_user_id, plan.plan_date)
    from app.core.cache import invalidate_user_training
    invalidate_user_training(child_user_id, plan_date=plan.plan_date)

    from app.services.training.service import _get_plan_by_date, _plan_to_response
    plan = _get_plan_by_date(db, child_user_id, plan.plan_date)
    return _plan_to_response(plan, db=db)

def customize_plan_items(
    db: Session,
    child_user_id: int,
    plan_id: int,
    skills: list[str],
) -> dict:
    """整体替换今日训练方案中的项目（不改技能等级进度）

    约束：
    - skills 列表长度必须等于原方案 items 数量
    - 每个技能取用户当前的 oss_stage/oss_part → 从 OSS 池找对应音频
    - 找不到音频 → 占位符
    - 选修项不受影响
    """
    from app.services.content_meta import (
        content_display_title,
        estimate_duration_min,
        item_instruction,
        parse_item_meta,
    )
    from app.services.talent_content_pool import get_talent_content_pool
    from app.services.child_training_state import (
        REQUIRED_SKILLS,
        get_skill_oss_position,
        get_training_progress,
    )
    from app.services.assessment_service import resolve_effective_talent
    from app.services.training_catalog_sync import repair_plan_media_items
    from app.services.training_child_guide import build_coach_text_for_plan

    plan = db.get(TrainingPlan, plan_id)
    if not plan or plan.child_user_id != child_user_id:
        raise TrainingError("训练计划不存在", 404)
    if plan.status == "completed":
        raise TrainingError("今日训练已完成，无法修改", 403)

    from app.services.training.common import _user_now
    from app.services.training.service import (
        _mutable_required_items,
        _plan_has_any_checkin,
    )

    now = _user_now(db, child_user_id)
    if is_plan_globally_cutoff(plan, now=now):
        raise TrainingError("训练日已于凌晨4点截止", 403)
    if getattr(plan, "plan_customized", 0):
        raise TrainingError("今日方案已编辑过，每个训练日仅可修改一次", 403)

    mutable = _mutable_required_items(plan)
    if not mutable:
        raise TrainingError("当前没有可编辑的必修项", 400)
    if _plan_has_any_checkin(db, plan):
        raise TrainingError("已有打卡记录，无法编辑方案", 403)

    items = sorted(plan.items, key=lambda x: x.sort_order)
    if len(skills) != len(mutable):
        raise TrainingError(
            f"需要 {len(mutable)} 个技能（当前待打卡项数），实际提交 {len(skills)} 个",
            400,
        )

    # 校验技能名合法
    cur = __import__("config.loader", fromlist=["load_training_curriculum"]).load_training_curriculum()
    elective_rules = cur.get("elective_rules") or {}
    elective_skills = set(elective_rules.keys())
    allowed_skills = set(REQUIRED_SKILLS) | elective_skills
    for sk in skills:
        if sk not in allowed_skills:
            raise TrainingError(f"未知技能：{sk}", 400)

    # 获取用户天赋 + OSS 池
    talent = resolve_effective_talent(db, child_user_id)
    if not talent or not talent.get("talent_code"):
        raise TrainingError("请先完成天赋测评", 403)
    talent_code = talent["talent_code"]

    child = db.get(ChildUser, child_user_id)
    state = get_training_progress(child) if child else {}
    pool = get_talent_content_pool(db, talent_code)

    def _find_content(skill_name: str) -> tuple:
        """从 OSS 池找该技能当前 OSS 位置对应的音频"""
        stage, part = get_skill_oss_position(state, skill_name)
        for item in pool:
            meta = parse_item_meta(item)
            if meta.get("skill") == skill_name:
                s = meta.get("stage", 0)
                p = meta.get("part", 0)
                if s == stage and p == part:
                    return item, stage, part
        # fallback: 任意第一个
        for item in pool:
            meta = parse_item_meta(item)
            if meta.get("skill") == skill_name:
                return item, meta.get("stage", 0), meta.get("part", 0)
        return None, stage, part

    # 逐个替换 mutable 项
    for i, target_item in enumerate(mutable):
        skill_name = skills[i]
        is_elective = skill_name in elective_rules

        content, stage, part = _find_content(skill_name)
        if content:
            meta = parse_item_meta(content)
            inst = item_instruction("A", meta.get("content_type") or "audio")
            try:
                payload = json.loads(inst)
                payload["skill"] = meta.get("skill") or skill_name
                payload["item_type"] = "elective" if is_elective else "required"
                payload["oss_stage"] = stage
                payload["oss_part"] = part
                inst = json.dumps(payload, ensure_ascii=False)
            except Exception:
                pass
            target_item.title = content_display_title(content)
            target_item.audio_url = content.play_url
            target_item.video_url = content.video_url
            target_item.duration_min = estimate_duration_min(content)
            target_item.content_item_id = content.id
            target_item.instructions = inst
            target_item.ability_type = "audio"
        else:
            target_item.title = f"{skill_name}（待同步）"
            target_item.audio_url = None
            target_item.video_url = None
            target_item.duration_min = 0
            target_item.content_item_id = None
            target_item.instructions = item_instruction("A", "placeholder")
            target_item.ability_type = "placeholder"

    # 匹配视频（极速运算等）
    from app.services.training_schedule_service import _attach_videos_to_items
    _attach_videos_to_items(db, plan)

    repair_plan_media_items(db, plan, talent_code)
    plan.report_text = build_coach_text_for_plan(plan)
    plan.plan_customized = 1
    db.commit()

    invalidate_plan_cache(child_user_id, plan.plan_date)
    from app.core.cache import invalidate_user_training
    invalidate_user_training(child_user_id, plan_date=plan.plan_date)

    from app.services.training.service import _get_plan_by_date, _plan_to_response
    plan = _get_plan_by_date(db, child_user_id, plan.plan_date)
    return _plan_to_response(plan, db=db)

