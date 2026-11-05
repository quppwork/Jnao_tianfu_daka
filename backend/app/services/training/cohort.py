"""学员分群 + 方案模式解析（今日修炼入口）。

显式 profile 优先；否则按档案信号自动推断。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ChildUser
from config.loader import load_training_recipes

VALID_COHORTS = frozenset(
    {"experience", "venue_new", "new_student", "regular", "rocket", "blackhorse"}
)
VALID_PLAN_MODES = frozenset(
    {"standard", "academic", "rocket", "blackhorse", "custom"}
)
VALID_MIX_PREF = frozenset({"fill_default", "fill_prefer", "academic"})
VALID_VARIANTS = frozenset({"standard", "advanced", "fixed", "adult"})

_COHORT_ALIASES = {
    "体验": "experience",
    "体验学员": "experience",
    "会场": "venue_new",
    "会场新学员": "venue_new",
    "新学员": "new_student",
    "新": "new_student",
    "老学员": "regular",
    "老": "regular",
    "火箭": "rocket",
    "火箭营": "rocket",
    "黑马": "blackhorse",
    "黑马营": "blackhorse",
}
_MODE_ALIASES = {
    "标准": "standard",
    "标准训练": "standard",
    "学业": "academic",
    "学业规划": "academic",
    "火箭": "rocket",
    "火箭营": "rocket",
    "黑马": "blackhorse",
    "黑马营": "blackhorse",
    "定制": "custom",
    "个性化": "custom",
}


@dataclass(frozen=True)
class CohortContext:
    cohort: str
    plan_mode: str
    mix_preference: str
    brain_ratio: float
    subject_ratio: float
    source: str  # explicit | inferred | default
    recipe_variant: str  # standard | advanced | fixed | adult


def _profile(child: ChildUser | None) -> dict:
    if not child:
        return {}
    pj = child.profile_json
    return pj if isinstance(pj, dict) else {}


def _training_block(pj: dict) -> dict:
    tr = pj.get("training")
    return tr if isinstance(tr, dict) else {}


def _norm_token(raw: Any) -> str:
    return str(raw or "").strip().lower()


def _match_flag(value: str, flags: list) -> bool:
    if not value:
        return False
    for f in flags or []:
        fl = str(f).strip().lower()
        if fl and (value == fl or fl in value or value in fl):
            return True
    return False


def _has_confirmed_academic(db: Session | None, child_user_id: int | None) -> bool:
    if db is None or not child_user_id:
        return False
    try:
        from app.services.academic_plan_service import get_confirmed_plan

        row = get_confirmed_plan(db, child_user_id)
        return bool(row and (row.status or "") == "confirmed")
    except Exception:
        return False


def _training_days(child: ChildUser | None) -> int:
    if not child:
        return 0
    try:
        from app.services.child_training_state import get_training_progress

        return int(get_training_progress(child).get("training_days") or 0)
    except Exception:
        return 0


def _explicit_cohort(pj: dict, tr: dict) -> str | None:
    raw = tr.get("cohort") or pj.get("cohort") or ""
    key = _norm_token(raw)
    if key in _COHORT_ALIASES:
        key = _COHORT_ALIASES[key]
    if key in VALID_COHORTS:
        return key
    return None


def _infer_cohort(child: ChildUser | None, pj: dict, tr: dict) -> tuple[str, str]:
    """返回 (cohort, source)。"""
    recipes = load_training_recipes()
    auto = recipes.get("auto_infer") or {}
    camp = _norm_token(tr.get("camp") or tr.get("camp_type") or pj.get("camp") or "")
    channel = _norm_token(
        tr.get("channel")
        or pj.get("register_channel")
        or pj.get("channel")
        or ""
    )
    level = _norm_token(getattr(child, "training_level", None) or tr.get("level") or "")

    if _match_flag(camp, auto.get("blackhorse_flags") or []) or _match_flag(
        level, auto.get("blackhorse_flags") or []
    ):
        return "blackhorse", "inferred"
    if _match_flag(camp, auto.get("rocket_flags") or []) or _match_flag(
        level, auto.get("rocket_flags") or []
    ):
        return "rocket", "inferred"
    if _match_flag(camp, auto.get("venue_flags") or []) or _match_flag(
        channel, auto.get("venue_flags") or []
    ):
        return "venue_new", "inferred"
    if _match_flag(channel, auto.get("experience_channels") or []) or _match_flag(
        level, auto.get("experience_channels") or []
    ):
        return "experience", "inferred"

    days = _training_days(child)
    exp_max = int(auto.get("experience_max_days", 0))
    max_new = int(auto.get("new_student_max_days") or 7)
    # 全新学员默认体验路径（30/60/90 固定表），避免继续静默走旧权重
    if days <= exp_max:
        return "experience", "inferred"
    if days < max_new:
        return "new_student", "inferred"
    return "regular", "inferred"


def resolve_cohort(
    child: ChildUser | None,
    *,
    db: Session | None = None,
) -> str:
    pj = _profile(child)
    tr = _training_block(pj)
    explicit = _explicit_cohort(pj, tr)
    if explicit:
        return explicit
    cohort, _ = _infer_cohort(child, pj, tr)
    return cohort


def resolve_recipe_variant(child: ChildUser | None) -> str:
    pj = _profile(child)
    tr = _training_block(pj)
    raw = _norm_token(
        tr.get("recipe_variant") or tr.get("variant") or pj.get("recipe_variant") or ""
    )
    aliases = {
        "标准": "standard",
        "自动": "standard",
        "强化": "advanced",
        "高级": "advanced",
        "定制": "advanced",
        "固定": "fixed",
        "成人": "adult",
    }
    if raw in aliases:
        raw = aliases[raw]
    if raw in VALID_VARIANTS:
        return raw
    if tr.get("use_fixed_recipe") is True:
        return "fixed"
    cohort = _explicit_cohort(pj, tr)
    if not cohort:
        cohort, _ = _infer_cohort(child, pj, tr)
    cohorts = (load_training_recipes().get("cohorts") or {}).get(cohort) or {}
    default = str(cohorts.get("default_variant") or "standard")
    return default if default in VALID_VARIANTS else "standard"


def resolve_plan_mode(
    child: ChildUser | None,
    *,
    cohort: str | None = None,
    db: Session | None = None,
) -> str:
    pj = _profile(child)
    tr = _training_block(pj)
    raw = _norm_token(tr.get("plan_mode") or pj.get("plan_mode") or "")
    if raw in _MODE_ALIASES:
        raw = _MODE_ALIASES[raw]
    if raw in VALID_PLAN_MODES:
        return raw

    c = cohort or resolve_cohort(child, db=db)
    if c in ("rocket", "blackhorse", "venue_new"):
        return "rocket" if c != "blackhorse" else "blackhorse"

    if _has_confirmed_academic(db, getattr(child, "id", None)):
        return "academic"

    recipes = load_training_recipes()
    cohorts = recipes.get("cohorts") or {}
    cfg = cohorts.get(c) or {}
    default = str(cfg.get("default_plan_mode") or "standard")
    return default if default in VALID_PLAN_MODES else "standard"


def resolve_mix_preference(child: ChildUser | None, *, plan_mode: str) -> str:
    if plan_mode == "academic":
        return "academic"
    pj = _profile(child)
    tr = _training_block(pj)
    raw = _norm_token(tr.get("plan_mode_preference") or tr.get("mix_preference") or "")
    if raw in VALID_MIX_PREF:
        return raw
    return "fill_default"


def _mix_for_minutes(minutes: int, mix_pref: str) -> tuple[float, float]:
    recipes = load_training_recipes()
    bands = recipes.get("duration_mix") or []
    m = max(0, int(minutes))
    for band in bands:
        if not isinstance(band, dict):
            continue
        lo = int(band.get("minutes_min") or 0)
        hi = int(band.get("minutes_max") or 0)
        if m < lo or m > hi:
            continue
        modes = band.get("modes") or {}
        picked = modes.get(mix_pref) or modes.get("fill_default") or {}
        return float(picked.get("brain", 1.0)), float(picked.get("subject", 0.0))
    if mix_pref == "academic":
        return 0.5, 0.5
    return 1.0, 0.0


def build_cohort_context(
    child: ChildUser | None,
    *,
    planned_minutes: int,
    db: Session | None = None,
) -> CohortContext:
    pj = _profile(child)
    tr = _training_block(pj)
    explicit = _explicit_cohort(pj, tr)
    if explicit:
        cohort, source = explicit, "explicit"
    else:
        cohort, source = _infer_cohort(child, pj, tr)
        if source == "inferred" and cohort == "regular" and not (
            tr.get("camp") or pj.get("camp") or tr.get("channel") or pj.get("channel")
        ):
            # 无任何信号时保持现网默认 regular，标记 default
            source = "default"

    plan_mode = resolve_plan_mode(child, cohort=cohort, db=db)
    # 显式 plan_mode 也算 explicit 来源
    if tr.get("plan_mode") or pj.get("plan_mode"):
        source = "explicit"
    mix_pref = resolve_mix_preference(child, plan_mode=plan_mode)
    variant = resolve_recipe_variant(child)

    if plan_mode == "standard" and mix_pref == "fill_default":
        brain, subject = 1.0, 0.0
    else:
        brain, subject = _mix_for_minutes(planned_minutes, mix_pref)

    return CohortContext(
        cohort=cohort,
        plan_mode=plan_mode,
        mix_preference=mix_pref,
        brain_ratio=brain,
        subject_ratio=subject,
        source=source,
        recipe_variant=variant,
    )


def cohort_to_dict(ctx: CohortContext) -> dict[str, Any]:
    return {
        "cohort": ctx.cohort,
        "plan_mode": ctx.plan_mode,
        "mix_preference": ctx.mix_preference,
        "brain_ratio": ctx.brain_ratio,
        "subject_ratio": ctx.subject_ratio,
        "cohort_source": ctx.source,
        "recipe_variant": ctx.recipe_variant,
    }
