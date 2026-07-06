"""学员训练进度 — v2.0 多技能并行 Tier 独立晋级 + OSS stage/part + 连续达标计数

数据结构（存 profile_json.training_progress）：

{
    "skills": {
        "超脑阅读": { "tier": 1, "oss_stage": 0, "oss_part": 0, "consecutive_pass": 0,
                     "part_listen_count": 0, "part_first_listen_at": null },
        "影像追忆": { "tier": 1, "oss_stage": 1, "oss_part": 1, "consecutive_pass": 0,
                     "part_listen_count": 0, "part_first_listen_at": null },
        "扫描速记": { "tier": 1, "oss_stage": 1, "oss_part": 1, "consecutive_pass": 0 },
        "极速运算": { "tier": 1, "oss_stage": 2, "oss_part": 1, "consecutive_pass": 0 },
        "极速学习": { "tier": 1, "oss_stage": 2, "oss_part": 1, "consecutive_pass": 0 }
    },
    "training_days": 0,
    "training_day_anchor": null,
    "last_settled_plan_date": null
}

overall_tier = min(所有活跃技能的 tier)  ← 最低原则
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.db.models import ChildUser

STATE_KEY = "training_progress"

# 5 个必修技能
REQUIRED_SKILLS = ("超脑阅读", "影像追忆", "扫描速记", "极速运算", "极速学习")

# OSS 默认起始位置（通用；极速学习行者/德者从 stage 3 开始由 OSS 查询时动态调整）
DEFAULT_OSS_START: dict[str, tuple[int, int]] = {
    "超脑阅读": (0, 0),   # 单音频，无阶段
    "影像追忆": (1, 1),
    "扫描速记": (1, 1),
    "极速运算": (2, 1),
    "极速学习": (2, 1),   # 行者/德者后续由 OSS 池查询覆盖为 (3, 1)
}


def _default_state(talent_code: int | None = None) -> dict:
    """新用户默认初始状态。

    Args:
        talent_code: 天赋代码 1-5，极速学习的起始 OSS stage 因天赋而异：
                     学者(1)/思者(2)/赢者(5) → stage 2
                     行者(3)/德者(4) → stage 3
    """
    skills = {}
    for sk in REQUIRED_SKILLS:
        stage, part = DEFAULT_OSS_START[sk]
        # 极速学习：行者(3)/德者(4) 从 stage 3 开始
        if sk == "极速学习" and talent_code in (3, 4):
            stage = 3
        skills[sk] = {
            "tier": 1,
            "oss_stage": stage,
            "oss_part": part,
            "consecutive_pass": 0,
            "part_listen_count": 0,
            "part_first_listen_at": None,
        }
    return {
        "skills": skills,
        "training_days": 0,
        "training_day_anchor": None,
        "last_settled_plan_date": None,
    }


# ─── 读写 ──────────────────────────────────────────


def get_training_progress(child: ChildUser) -> dict:
    """从 child.profile_json 读取训练进度，缺失则返回默认"""
    pj = child.profile_json if isinstance(child.profile_json, dict) else {}
    raw = pj.get(STATE_KEY)
    if not isinstance(raw, dict):
        return _default_state()
    skills_raw = raw.get("skills") or {}
    skills = {}
    for sk in REQUIRED_SKILLS:
        sd = skills_raw.get(sk) or {}
        skills[sk] = {
            "tier": int(sd.get("tier") or 1),
            "oss_stage": int(sd.get("oss_stage") if sd.get("oss_stage") is not None else DEFAULT_OSS_START.get(sk, (0, 0))[0]),
            "oss_part": int(sd.get("oss_part") if sd.get("oss_part") is not None else DEFAULT_OSS_START.get(sk, (0, 0))[1]),
            "consecutive_pass": int(sd.get("consecutive_pass") or 0),
            "part_listen_count": int(sd.get("part_listen_count") or 0),
            "part_first_listen_at": sd.get("part_first_listen_at"),
        }
    return {
        "skills": skills,
        "training_days": int(raw.get("training_days") or 0),
        "training_day_anchor": raw.get("training_day_anchor"),
        "last_settled_plan_date": raw.get("last_settled_plan_date"),
    }


def save_training_progress(db: Session, child: ChildUser, state: dict) -> dict:
    """写入 profile_json.training_progress"""
    pj = dict(child.profile_json or {})
    pj[STATE_KEY] = {
        "skills": _clean_skills_for_save(state.get("skills") or {}),
        "training_days": int(state.get("training_days") or 0),
        "training_day_anchor": state.get("training_day_anchor"),
        "last_settled_plan_date": state.get("last_settled_plan_date"),
    }
    child.profile_json = pj
    db.flush()
    return pj[STATE_KEY]


def _clean_skills_for_save(skills: dict) -> dict:
    """保存前清理：只保留 REQUIRED_SKILLS + 必要字段"""
    out = {}
    for sk in REQUIRED_SKILLS:
        if sk in skills:
            sd = skills[sk]
            out[sk] = {
                "tier": int(sd.get("tier") or 1),
                "oss_stage": int(sd.get("oss_stage") or 0),
                "oss_part": int(sd.get("oss_part") or 0),
                "consecutive_pass": int(sd.get("consecutive_pass") or 0),
                "part_listen_count": int(sd.get("part_listen_count") or 0),
                "part_first_listen_at": sd.get("part_first_listen_at"),
            }
    return out


# ─── 整体 Tier ──────────────────────────────────────

def overall_tier(state: dict) -> int:
    """取所有技能 tier 的平均值后向下取整。

    例: [1, 2, 3] → avg=2.0 → 2
         [1, 1, 2, 2, 2] → avg=1.6 → 1
         [5, 5, 3, 1, 1] → avg=3.0 → 3
    """
    skills = state.get("skills") or {}
    tiers = [sd.get("tier", 1) for sd in skills.values() if isinstance(sd, dict)]
    if not tiers:
        return 1
    import math
    return math.floor(sum(tiers) / len(tiers))


# ─── 按打卡记录过滤活跃技能 ───────────────────────────

def get_skills_with_records(db: Session, child_user_id: int) -> set[str]:
    """查询该用户在 TrainingRecord 中有打卡记录的技能名"""
    import json as _json
    from sqlalchemy import select
    from app.db.models import TrainingRecord, TrainingItem, ContentItem
    from app.services.content_meta import parse_item_meta

    rows = db.execute(
        select(TrainingItem.instructions, TrainingItem.content_item_id)
        .join(TrainingRecord, TrainingRecord.item_id == TrainingItem.id)
        .where(TrainingRecord.child_user_id == child_user_id)
        .distinct()
    ).all()

    skills: set[str] = set()
    for instructions, content_item_id in rows:
        if instructions and str(instructions).strip().startswith("{"):
            try:
                payload = _json.loads(instructions)
                sk = (payload.get("skill") or "").strip()
                if sk and sk in REQUIRED_SKILLS:
                    skills.add(sk)
                    continue
            except _json.JSONDecodeError:
                pass
        # fallback: 从 content_item 元数据取 skill
        if content_item_id:
            ci = db.get(ContentItem, content_item_id)
            if ci:
                meta = parse_item_meta(ci)
                sk = meta.get("skill")
                if sk and sk in REQUIRED_SKILLS:
                    skills.add(sk)
    return skills


def filter_active_skills(state: dict, skills_with_records: set[str]) -> dict:
    """只保留有打卡记录的技能，用于 overall_tier 计算"""
    if not skills_with_records:
        return state  # 无记录 → 保留全部（新用户场景）
    all_skills = state.get("skills") or {}
    filtered = {sk: all_skills[sk] for sk in REQUIRED_SKILLS if sk in skills_with_records and sk in all_skills}
    if not filtered:
        return state  # 意外兜底
    new_state = dict(state)
    new_state["skills"] = filtered
    return new_state


# ─── 单个技能状态 ───────────────────────────────────

def get_skill_state(state: dict, skill: str) -> dict:
    """读取单个技能的状态；不存在则返回默认"""
    skills = state.get("skills") or {}
    if skill in skills:
        return dict(skills[skill])
    default = DEFAULT_OSS_START.get(skill, (0, 0))
    return {"tier": 1, "oss_stage": default[0], "oss_part": default[1], "consecutive_pass": 0,
            "part_listen_count": 0, "part_first_listen_at": None}


def get_skill_tier(state: dict, skill: str) -> int:
    return get_skill_state(state, skill).get("tier", 1)


def get_skill_oss_position(state: dict, skill: str) -> tuple[int, int]:
    sd = get_skill_state(state, skill)
    return sd.get("oss_stage", 0), sd.get("oss_part", 0)


def get_consecutive_pass(state: dict, skill: str) -> int:
    return get_skill_state(state, skill).get("consecutive_pass", 0)


# ─── 写入 ──────────────────────────────────────────

def set_skill_tier(state: dict, skill: str, tier: int) -> None:
    """设置技能 Tier（晋级时调用）"""
    skills = state.setdefault("skills", {})
    if skill not in skills:
        skills[skill] = {"tier": 1, "oss_stage": 0, "oss_part": 0, "consecutive_pass": 0}
    skills[skill]["tier"] = tier


def set_skill_oss_position(state: dict, skill: str, stage: int, part: int) -> None:
    """设置技能 OSS 位置"""
    skills = state.setdefault("skills", {})
    if skill not in skills:
        skills[skill] = {"tier": 1, "oss_stage": stage, "oss_part": part, "consecutive_pass": 0}
    skills[skill]["oss_stage"] = stage
    skills[skill]["oss_part"] = part


def set_consecutive_pass(state: dict, skill: str, count: int) -> None:
    """设置连续达标计数"""
    skills = state.setdefault("skills", {})
    if skill not in skills:
        skills[skill] = {"tier": 1, "oss_stage": 0, "oss_part": 0, "consecutive_pass": 0}
    skills[skill]["consecutive_pass"] = max(0, count)


# ─── 晋级操作 ──────────────────────────────────────

def bump_consecutive_pass(state: dict, skill: str) -> int:
    """达标 → consecutive_pass += 1；返回新计数"""
    skills = state.setdefault("skills", {})
    if skill not in skills:
        skills[skill] = {"tier": 1, "oss_stage": 0, "oss_part": 0, "consecutive_pass": 0}
    skills[skill]["consecutive_pass"] = int(skills[skill].get("consecutive_pass", 0)) + 1
    return skills[skill]["consecutive_pass"]


def reset_consecutive_pass(state: dict, skill: str) -> None:
    """不达标 → 计数重置为 0"""
    set_consecutive_pass(state, skill, 0)


def advance_skill_tier(state: dict, skill: str) -> int:
    """技能 Tier += 1，consecutive_pass 重置为 0，part 轮换计数器归零；返回新 Tier"""
    current = get_skill_tier(state, skill)
    new_tier = current + 1
    set_skill_tier(state, skill, new_tier)
    reset_consecutive_pass(state, skill)
    # 晋级后 part 轮换计数器归零
    sd = state.get("skills", {}).get(skill)
    if sd:
        sd["part_listen_count"] = 0
        sd["part_first_listen_at"] = None
    return new_tier


# ─── 训练日 ────────────────────────────────────────

def training_day_number(state: dict) -> int:
    return int(state.get("training_days") or 0) + 1


def bump_training_completed_day(state: dict) -> int:
    state["training_days"] = int(state.get("training_days") or 0) + 1
    return state["training_days"]


# ─── 通用 helper ──────────────────────────────────

def child_grade(child) -> str | None:
    """从 ChildUser 读取年级（profile_json.grade / learner.grade）"""
    pj = child.profile_json if isinstance(child.profile_json, dict) else {}
    learner = pj.get("learner") if isinstance(pj.get("learner"), dict) else {}
    return pj.get("grade") or learner.get("grade") or getattr(child, "grade", None) or None


# ─── 序列化 helper（供 API 返回）────────────────────

def state_summary(state: dict) -> dict:
    """返回可序列化的状态摘要"""
    skills_summary = {}
    for sk in REQUIRED_SKILLS:
        sd = get_skill_state(state, sk)
        skills_summary[sk] = {
            "tier": sd["tier"],
            "oss_stage": sd["oss_stage"],
            "oss_part": sd["oss_part"],
            "consecutive_pass": sd["consecutive_pass"],
        }
    return {
        "overall_tier": overall_tier(state),
        "skills": skills_summary,
        "training_days": state.get("training_days", 0),
    }


# ─── 老学员 onboarding 初始化 ──────────────────────

SKIP_INIT_SKILLS = frozenset({"极速学习"})  # 待完工


def build_state_from_onboarding(
    db: Session,
    child: ChildUser,
    talent_code: int,
    prior_abilities: list[str],
    prior_training_data: dict,
) -> dict:
    """老学员 onboarding 完成后，根据历史数据初始化 training_progress。

    对每个已填写的技能，用 evaluate_card 判定其最近一次数据是否达到 Tier 1 标准：
    - 达标 + totalCount ≥ 3 → Tier 2, consecutive_pass=3, OSS 推进（直接视为完成3连达标）
    - 达标 + totalCount < 3 → Tier 2, consecutive_pass=1, OSS 推进
    - 不达标或未填 → 保持 Tier 1（默认）
    """
    from app.services.training_mastery import evaluate_card, bump_oss_after_pass

    state = _default_state(talent_code)
    grade = child_grade(child)
    grade_band = _grade_band_from_grade(grade)

    for skill in prior_abilities:
        if skill not in REQUIRED_SKILLS or skill in SKIP_INIT_SKILLS:
            continue
        data = prior_training_data.get(skill) or {}
        # ── sanitize ──
        try:
            word_count = abs(int(data.get("wordCount") or 0))
            minutes = abs(int(data.get("time") or 0))
            acc = data.get("accuracy_pct")
            acc = max(0, min(int(acc), 100)) if acc else None
            total_cnt = abs(int(data.get("totalCount") or 0))
        except (ValueError, TypeError):
            continue

        if not word_count and skill in ("超脑阅读", "影像追忆", "扫描速记"):
            continue  # 缺字数，判不了
        if minutes == 0:
            minutes = 1  # 防除零

        card = {"name": skill, "wordCount": word_count, "time": minutes}
        if acc is not None:
            card["accuracy"] = acc

        result = evaluate_card(skill, tier=1, grade_band=grade_band, card=card)
        if result.get("passed"):
            state["skills"][skill]["tier"] = 2
            bump_oss_after_pass(db, talent_code, state, skill)
            state["skills"][skill]["consecutive_pass"] = 3 if total_cnt >= 3 else 1

    save_training_progress(db, child, state)
    return state


def _grade_band_from_grade(grade: str | None) -> str | None:
    """从年级字符串解析学段（内联实现，避免循环依赖）"""
    from config.loader import load_training_tier_thresholds

    th = load_training_tier_thresholds()
    bands = th.get("grade_bands") or {}
    g = (grade or "").strip()
    if not g:
        return None
    for band, grades in bands.items():
        if g in grades:
            return band
    return None


# ─── Part 轮换 ──────────────────────────────────────


PART_ROTATION_NEW_USER = 5          # 新学员 5 次打卡换 part
PART_ROTATION_RETURNING_7D = 20     # 老学员 7 天内 20 次换 part
PART_ROTATION_RETURNING_7D_PLUS = 14  # 老学员超 7 天 14 次换 part


def rotate_part_after_checkin(
    state: dict,
    skill: str,
    *,
    student_type: str = "new",
    db: Session | None = None,
    talent_code: int | None = None,
) -> bool:
    """打卡后判定当前技能的 part 是否需要轮换。返回 True 表示轮换了。"""
    sd = state["skills"].get(skill)
    if not sd:
        return False

    count = int(sd.get("part_listen_count", 0)) + 1
    sd["part_listen_count"] = count

    threshold = _part_rotation_threshold(student_type, sd)
    if count < threshold:
        return False

    # 执行轮换
    return _do_rotate_part(state, skill, db=db, talent_code=talent_code)


def _part_rotation_threshold(student_type: str, sd: dict) -> int:
    """判定当前 part 的轮换阈值"""
    if student_type == "new":
        return PART_ROTATION_NEW_USER
    first_at = sd.get("part_first_listen_at")
    if first_at:
        from datetime import datetime, timezone, timedelta

        try:
            first = first_at if isinstance(first_at, datetime) else datetime.fromisoformat(str(first_at))
            now = datetime.now(timezone(timedelta(hours=8)))
            days = (now - first).days
            if days <= 7:
                return PART_ROTATION_RETURNING_7D
        except (ValueError, TypeError):
            pass
    return PART_ROTATION_RETURNING_7D_PLUS


def _do_rotate_part(
    state: dict,
    skill: str,
    *,
    db: Session | None = None,
    talent_code: int | None = None,
) -> bool:
    """执行 part 轮换：只在本 stage 内循环 part，不改 stage。

    stage 推进由晋级体系统一管理（bump_oss_after_pass），不在此处处理。
    """
    sd = state["skills"].get(skill)
    if not sd:
        return False

    stage = int(sd.get("oss_stage", 0))
    part = int(sd.get("oss_part", 0))

    if db and talent_code:
        from app.services.talent_content_pool import get_talent_content_pool
        from app.services.training_curriculum import _find_lesson

        pool = get_talent_content_pool(db, talent_code)

        # 当前 stage 的下一个 part
        nxt = _find_lesson(pool, skill, stage, part + 1)
        if nxt:
            sd["oss_part"] = part + 1
            _reset_part_counters(sd)
            return True

        # 当前 stage 无更多 part → 回到 part=1 重新循环
        first = _find_lesson(pool, skill, stage, 1)
        if first:
            sd["oss_part"] = 1
            _reset_part_counters(sd)
            return True
    else:
        sd["oss_part"] = part + 1
        _reset_part_counters(sd)
        return True

    return False


def _reset_part_counters(sd: dict) -> None:
    """轮换后重置计数"""
    from datetime import datetime, timezone, timedelta

    sd["part_listen_count"] = 0
    sd["part_first_listen_at"] = datetime.now(timezone(timedelta(hours=8))).isoformat()
