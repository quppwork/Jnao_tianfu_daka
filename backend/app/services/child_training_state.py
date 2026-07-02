"""学员训练进度 — v2.0 多技能并行 Tier 独立晋级 + OSS stage/part + 连续达标计数

数据结构（存 profile_json.training_progress）：

{
    "skills": {
        "超脑阅读": { "tier": 1, "oss_stage": 0, "oss_part": 0, "consecutive_pass": 0 },
        "影像追忆": { "tier": 1, "oss_stage": 1, "oss_part": 1, "consecutive_pass": 0 },
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
            }
    return out


# ─── 整体 Tier ──────────────────────────────────────

def overall_tier(state: dict) -> int:
    """最低原则：取所有活跃技能中最低的 Tier"""
    skills = state.get("skills") or {}
    tiers = [sd.get("tier", 1) for sd in skills.values() if isinstance(sd, dict)]
    return min(tiers) if tiers else 1


# ─── 单个技能状态 ───────────────────────────────────

def get_skill_state(state: dict, skill: str) -> dict:
    """读取单个技能的状态；不存在则返回默认"""
    skills = state.get("skills") or {}
    if skill in skills:
        return dict(skills[skill])
    default = DEFAULT_OSS_START.get(skill, (0, 0))
    return {"tier": 1, "oss_stage": default[0], "oss_part": default[1], "consecutive_pass": 0}


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
    """技能 Tier += 1，consecutive_pass 重置为 0；返回新 Tier"""
    current = get_skill_tier(state, skill)
    new_tier = current + 1
    set_skill_tier(state, skill, new_tier)
    reset_consecutive_pass(state, skill)
    return new_tier


# ─── 训练日 ────────────────────────────────────────

def training_day_number(state: dict) -> int:
    return int(state.get("training_days") or 0) + 1


def bump_training_completed_day(state: dict) -> int:
    state["training_days"] = int(state.get("training_days") or 0) + 1
    return state["training_days"]


# ─── 通用 helper ──────────────────────────────────

def child_grade(child) -> str | None:
    """从 ChildUser 读取年级（profile_json.grade 或 direct grade 字段）"""
    pj = child.profile_json if isinstance(child.profile_json, dict) else {}
    return pj.get("grade") or getattr(child, "grade", None) or None


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
