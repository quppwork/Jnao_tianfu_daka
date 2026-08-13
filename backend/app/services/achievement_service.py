"""成就/荣誉系统服务 — 勋章定义、解锁逻辑、展柜管理"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AchievementDefinition,
    AchievementShowcase,
    ChildUser,
    TalentAssessment,
    TrainingRecord,
    UserAchievement,
    UserTitle,
)


class AchievementError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


_TIER_CN = {
    1: "一阶", 2: "二阶", 3: "三阶", 4: "四阶", 5: "五阶",
    6: "六阶", 7: "七阶", 8: "八阶", 9: "九阶",
}


def _tier_cn(tier: int) -> str:
    return _TIER_CN.get(tier, f"第{tier}阶")


def _format_progress_text(defn: AchievementDefinition, current: int, target: int, status: str) -> str:
    if defn.condition_json.get("type") == "skill_tier":
        return f"当前{_tier_cn(current)}，目标{_tier_cn(target)}"
    if target > 1:
        return f"{current}/{target}"
    return "已完成" if status != "locked" else "未完成"


# ─── 勋章定义初始化 ────────────────────────────────────────

DEFAULT_ACHIEVEMENTS = [
    # 连续打卡系列
    {"code": "streak_1", "name": "初露锋芒", "title": "新芽", "description": "完成首次天赋测评，开始认识自己", "category": "streak", "condition_json": {"type": "assessment", "count": 1}, "color_theme": "green", "sort_order": 1},
    {"code": "streak_3", "name": "小有所成", "title": "晨星", "description": "连续 3 天完成训练打卡", "category": "streak", "condition_json": {"type": "streak", "days": 3}, "color_theme": "yellow", "sort_order": 2},
    {"code": "streak_7", "name": "初窥门径", "title": "逐光者", "description": "连续 7 天完成训练打卡", "category": "streak", "condition_json": {"type": "streak", "days": 7}, "color_theme": "yellow", "sort_order": 3},
    {"code": "streak_14", "name": "日渐精进", "title": "执炬者", "description": "连续 14 天完成训练打卡", "category": "streak", "condition_json": {"type": "streak", "days": 14}, "color_theme": "yellow", "sort_order": 4},
    {"code": "streak_21", "name": "独当一面", "title": "破晓", "description": "连续 21 天完成训练打卡", "category": "streak", "condition_json": {"type": "streak", "days": 21}, "color_theme": "yellow", "sort_order": 5},
    # 技能专精系列
    {"code": "skill_speed_reading_t3", "name": "超脑阅读·速览", "title": "过目", "description": "超脑阅读达到三阶", "category": "skill", "condition_json": {"type": "skill_tier", "skill": "超脑阅读", "tier": 3}, "color_theme": "blue", "sort_order": 10},
    {"code": "skill_memory_t3", "name": "影像追忆·定格", "title": "留影", "description": "影像追忆达到三阶", "category": "skill", "condition_json": {"type": "skill_tier", "skill": "影像追忆", "tier": 3}, "color_theme": "blue", "sort_order": 11},
    {"code": "skill_scan_t3", "name": "扫描速记·洞察", "title": "览微", "description": "扫描速记达到三阶", "category": "skill", "condition_json": {"type": "skill_tier", "skill": "扫描速记", "tier": 3}, "color_theme": "blue", "sort_order": 12},
    # 天赋觉醒系列
    {"code": "talent_first", "name": "天赋觉醒·初阶", "title": "启明", "description": "五者天赋测评完成并查看报告", "category": "talent", "condition_json": {"type": "assessment_view", "count": 1}, "color_theme": "purple", "sort_order": 20},
    {"code": "talent_persist_7", "name": "天赋觉醒·进阶", "title": "明道", "description": "天赋测评完成 7 天后仍持续训练", "category": "talent", "condition_json": {"type": "persist_after_assessment", "days": 7}, "color_theme": "purple", "sort_order": 21},
    # 里程碑系列
    {"code": "milestone_100", "name": "百日筑基", "title": "归一", "description": "累计完成 100 天训练打卡", "category": "milestone", "condition_json": {"type": "total_checkin", "count": 100}, "color_theme": "pink", "sort_order": 100},
]


def init_achievement_definitions(db: Session) -> int:
    """初始化勋章定义（幂等，并同步文案）"""
    count = 0
    for data in DEFAULT_ACHIEVEMENTS:
        existing = db.scalar(
            select(AchievementDefinition).where(AchievementDefinition.code == data["code"])
        )
        if not existing:
            achievement = AchievementDefinition(**data)
            db.add(achievement)
            count += 1
        else:
            existing.name = data["name"]
            existing.title = data["title"]
            existing.description = data["description"]
    db.commit()
    from app.core.cache import cache_delete_prefix
    cache_delete_prefix("jnao:ach:list:")
    return count


# ─── 用户勋章查询 ────────────────────────────────────────

def get_user_achievements(db: Session, user_id: int) -> list[dict]:
    """获取用户所有勋章（含未解锁）"""
    # 获取所有激活的勋章定义
    definitions = db.scalars(
        select(AchievementDefinition)
        .where(AchievementDefinition.is_active == 1)
        .order_by(AchievementDefinition.sort_order)
    ).all()

    # 获取用户已有的勋章记录
    user_achievements = {
        ua.achievement_id: ua
        for ua in db.scalars(
            select(UserAchievement).where(UserAchievement.user_id == user_id)
        ).all()
    }

    result = []
    ctx = None
    for defn in definitions:
        ua = user_achievements.get(defn.id)
        if ua:
            status = ua.status
            progress_current = ua.progress_current
            progress_target = ua.progress_target
            unlocked_at = ua.unlocked_at
            claimed_at = ua.claimed_at
        else:
            if ctx is None:
                ctx = _load_progress_context(db, user_id)
            progress = _calculate_progress(db, user_id, defn, ctx)
            status = "ready" if progress["current"] >= progress["target"] else "locked"
            progress_current = progress["current"]
            progress_target = progress["target"]
            unlocked_at = None
            claimed_at = None

        result.append({
            "id": defn.id,
            "code": defn.code,
            "name": defn.name,
            "title": defn.title,
            "description": defn.description,
            "category": defn.category,
            "icon_url": defn.icon_url,
            "color_theme": defn.color_theme,
            "status": status,
            "progress_current": progress_current,
            "progress_target": progress_target,
            "progress_text": _format_progress_text(defn, progress_current, progress_target, status),
            "unlocked_at": unlocked_at.isoformat() if unlocked_at else None,
            "claimed_at": claimed_at.isoformat() if claimed_at else None,
        })

    return result


@dataclass(frozen=True)
class _ProgressContext:
    assessment_count: int
    streak_days: int
    persist_days: int
    total_checkin: int
    skill_tiers: dict[str, int]


def _load_progress_context(db: Session, user_id: int) -> _ProgressContext:
    """一次查出所有勋章共用的进度，避免每个勋章单独打库。"""
    from app.services.child_training_state import get_training_progress

    assessment_count = db.scalar(
        select(func.count(TalentAssessment.id)).where(
            TalentAssessment.child_user_id == user_id,
            TalentAssessment.report_json.isnot(None),
        )
    ) or 0

    skill_tiers: dict[str, int] = {}
    user = db.get(ChildUser, user_id)
    if user:
        progress = get_training_progress(user)
        for name, info in (progress.get("skills") or {}).items():
            if isinstance(info, dict):
                skill_tiers[name] = int(info.get("tier") or 1)

    return _ProgressContext(
        assessment_count=int(assessment_count),
        streak_days=_get_consecutive_checkin_days(db, user_id),
        persist_days=_get_training_days_after_assessment(db, user_id),
        total_checkin=int(
            db.scalar(
                select(func.count(TrainingRecord.id)).where(
                    TrainingRecord.child_user_id == user_id
                )
            ) or 0
        ),
        skill_tiers=skill_tiers,
    )


def _calculate_progress(
    db: Session,
    user_id: int,
    definition: AchievementDefinition,
    ctx: _ProgressContext | None = None,
) -> dict:
    """计算用户当前进度（可传入共享上下文，避免 N+1）"""
    if ctx is None:
        ctx = _load_progress_context(db, user_id)
    cond = definition.condition_json or {}
    cond_type = cond.get("type")

    if cond_type in ("assessment", "assessment_view"):
        return {"current": ctx.assessment_count, "target": cond.get("count", 1)}
    if cond_type == "streak":
        return {"current": ctx.streak_days, "target": cond.get("days", 1)}
    if cond_type == "skill_tier":
        skill = cond.get("skill")
        return {"current": ctx.skill_tiers.get(skill, 1), "target": cond.get("tier", 1)}
    if cond_type == "persist_after_assessment":
        return {"current": ctx.persist_days, "target": cond.get("days", 7)}
    if cond_type == "total_checkin":
        return {"current": ctx.total_checkin, "target": cond.get("count", 100)}
    return {"current": 0, "target": 1}


def _get_consecutive_checkin_days(db: Session, user_id: int) -> int:
    """计算连续打卡天数"""
    from datetime import date, timedelta
    from app.db.models import TrainingRecord

    today = date.today()
    check_dates = set()

    records = db.scalars(
        select(TrainingRecord.train_date)
        .where(TrainingRecord.child_user_id == user_id)
        .order_by(TrainingRecord.train_date.desc())
        .limit(60)
    ).all()

    for r in records:
        if r:
            check_dates.add(r)

    if not check_dates:
        return 0

    # 从今天开始往前数连续天数
    streak = 0
    check_date = today
    while check_date in check_dates:
        streak += 1
        check_date -= timedelta(days=1)

    return streak


def _get_training_days_after_assessment(db: Session, user_id: int) -> int:
    """计算测评后的训练天数"""
    from app.db.models import TalentAssessment, TrainingRecord
    from datetime import date, timedelta

    # 获取最近一次测评时间
    latest = db.scalar(
        select(TalentAssessment.assessed_at)
        .where(TalentAssessment.child_user_id == user_id)
        .order_by(TalentAssessment.assessed_at.desc())
        .limit(1)
    )
    if not latest:
        return 0

    assess_date = latest.date()
    today = date.today()

    # 计算测评后的训练天数
    count = db.scalar(
        select(func.count(func.distinct(TrainingRecord.train_date))).where(
            TrainingRecord.child_user_id == user_id,
            TrainingRecord.train_date >= assess_date,
        )
    ) or 0

    return count


# ─── 勋章解锁/领取 ────────────────────────────────────────

def check_and_update_achievements(db: Session, user_id: int) -> list[dict]:
    """检查并更新用户勋章状态（返回新解锁的勋章）"""
    newly_ready = []
    ctx = _load_progress_context(db, user_id)

    definitions = db.scalars(
        select(AchievementDefinition).where(AchievementDefinition.is_active == 1)
    ).all()

    user_achievements = {
        ua.achievement_id: ua
        for ua in db.scalars(
            select(UserAchievement).where(UserAchievement.user_id == user_id)
        ).all()
    }

    for defn in definitions:
        ua = user_achievements.get(defn.id)
        progress = _calculate_progress(db, user_id, defn, ctx)

        if ua:
            # 更新进度
            ua.progress_current = progress["current"]
            ua.progress_target = progress["target"]
            # 检查是否从 locked 变为 ready
            if ua.status == "locked" and progress["current"] >= progress["target"]:
                ua.status = "ready"
                ua.unlocked_at = datetime.now(timezone.utc)
                newly_ready.append({
                    "code": defn.code,
                    "name": defn.name,
                    "title": defn.title,
                })
        else:
            # 创建新记录
            status = "ready" if progress["current"] >= progress["target"] else "locked"
            ua = UserAchievement(
                user_id=user_id,
                achievement_id=defn.id,
                status=status,
                progress_current=progress["current"],
                progress_target=progress["target"],
                unlocked_at=datetime.now(timezone.utc) if status == "ready" else None,
            )
            db.add(ua)
            if status == "ready":
                newly_ready.append({
                    "code": defn.code,
                    "name": defn.name,
                    "title": defn.title,
                })

    db.commit()
    return newly_ready


def claim_achievement(db: Session, user_id: int, achievement_id: int) -> dict:
    """领取勋章（ready → claimed）"""
    ua = db.scalar(
        select(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement_id,
        )
    )

    if not ua:
        # 如果没有记录，先检查是否满足条件
        defn = db.get(AchievementDefinition, achievement_id)
        if not defn or not defn.is_active:
            raise AchievementError("勋章不存在或已下架", 404)

        progress = _calculate_progress(db, user_id, defn)
        if progress["current"] < progress["target"]:
            raise AchievementError("尚未满足解锁条件", 400)

        ua = UserAchievement(
            user_id=user_id,
            achievement_id=achievement_id,
            status="ready",
            progress_current=progress["current"],
            progress_target=progress["target"],
            unlocked_at=datetime.now(timezone.utc),
        )
        db.add(ua)
        db.flush()

    if ua.status == "locked":
        raise AchievementError("尚未满足解锁条件", 400)

    if ua.status == "claimed":
        raise AchievementError("已领取过该勋章", 400)

    ua.status = "claimed"
    ua.claimed_at = datetime.now(timezone.utc)
    db.commit()

    from app.core.cache import invalidate_user_achievement
    invalidate_user_achievement(user_id)

    defn = db.get(AchievementDefinition, achievement_id)
    return {
        "code": defn.code,
        "name": defn.name,
        "title": defn.title,
        "claimed_at": ua.claimed_at.isoformat(),
    }


# ─── 称号管理 ────────────────────────────────────────

def get_user_title(db: Session, user_id: int) -> dict | None:
    """获取用户当前称号"""
    ut = db.scalar(
        select(UserTitle).where(UserTitle.user_id == user_id, UserTitle.is_active == 1)
    )
    if not ut:
        return None

    # 查找对应的勋章定义
    defn = db.scalar(
        select(AchievementDefinition).where(AchievementDefinition.title == ut.title_code)
    )
    return {
        "title": ut.title_code,
        "name": defn.name if defn else ut.title_code,
        "color_theme": defn.color_theme if defn else None,
    }


def set_user_title(db: Session, user_id: int, title_code: str) -> dict:
    """设置用户称号（必须已解锁该勋章）"""
    # 查找对应的勋章
    defn = db.scalar(
        select(AchievementDefinition).where(AchievementDefinition.title == title_code)
    )
    if not defn:
        raise AchievementError("称号不存在", 404)

    # 检查是否已解锁
    ua = db.scalar(
        select(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == defn.id,
            UserAchievement.status == "claimed",
        )
    )
    if not ua:
        raise AchievementError("尚未解锁该称号对应的勋章", 400)

    # 设置称号
    ut = db.scalar(select(UserTitle).where(UserTitle.user_id == user_id))
    if ut:
        ut.title_code = title_code
        ut.is_active = 1
    else:
        ut = UserTitle(user_id=user_id, title_code=title_code, is_active=1)
        db.add(ut)

    db.commit()
    return {"title": title_code, "name": defn.name}


# ─── 荣誉展柜 ────────────────────────────────────────

def get_showcase(db: Session, user_id: int) -> list[dict]:
    """获取用户荣誉展柜（3个槽位）"""
    slots = db.scalars(
        select(AchievementShowcase)
        .where(AchievementShowcase.user_id == user_id)
        .order_by(AchievementShowcase.slot_index)
    ).all()

    slot_map = {s.slot_index: s for s in slots}
    result = []

    for i in range(3):
        slot = slot_map.get(i)
        if slot:
            defn = slot.achievement
            result.append({
                "slot": i,
                "achievement_id": defn.id,
                "code": defn.code,
                "name": defn.name,
                "title": defn.title,
                "icon_url": defn.icon_url,
                "color_theme": defn.color_theme,
            })
        else:
            result.append({"slot": i, "empty": True})

    return result


def set_showcase_slot(db: Session, user_id: int, slot_index: int, achievement_id: int | None) -> dict:
    """设置展柜槽位"""
    if slot_index < 0 or slot_index > 2:
        raise AchievementError("槽位索引无效", 400)

    # 查找现有槽位
    slot = db.scalar(
        select(AchievementShowcase).where(
            AchievementShowcase.user_id == user_id,
            AchievementShowcase.slot_index == slot_index,
        )
    )

    if achievement_id is None:
        # 清空槽位
        if slot:
            db.delete(slot)
            db.commit()
        return {"slot": slot_index, "empty": True}

    # 检查是否已解锁
    ua = db.scalar(
        select(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement_id,
            UserAchievement.status == "claimed",
        )
    )
    if not ua:
        raise AchievementError("只能展示已解锁的勋章", 400)

    if slot:
        slot.achievement_id = achievement_id
    else:
        slot = AchievementShowcase(
            user_id=user_id,
            slot_index=slot_index,
            achievement_id=achievement_id,
        )
        db.add(slot)

    db.commit()

    defn = db.get(AchievementDefinition, achievement_id)
    return {
        "slot": slot_index,
        "achievement_id": defn.id,
        "code": defn.code,
        "name": defn.name,
        "title": defn.title,
    }


# ─── 统计 ────────────────────────────────────────

def stats_from_items(items: list[dict]) -> dict:
    """从列表推导统计，避免额外 COUNT 查询"""
    total = len(items)
    claimed = sum(1 for i in items if i.get("status") == "claimed")
    ready = sum(1 for i in items if i.get("status") == "ready")
    return {
        "total": total,
        "claimed": claimed,
        "ready": ready,
        "locked": total - claimed - ready,
    }


def get_achievement_stats(db: Session, user_id: int) -> dict:
    """获取用户成就统计"""
    total = db.scalar(
        select(func.count(AchievementDefinition.id)).where(AchievementDefinition.is_active == 1)
    ) or 0

    claimed = db.scalar(
        select(func.count(UserAchievement.id)).where(
            UserAchievement.user_id == user_id,
            UserAchievement.status == "claimed",
        )
    ) or 0

    ready = db.scalar(
        select(func.count(UserAchievement.id)).where(
            UserAchievement.user_id == user_id,
            UserAchievement.status == "ready",
        )
    ) or 0

    return {
        "total": total,
        "claimed": claimed,
        "ready": ready,
        "locked": total - claimed - ready,
    }
