"""注册引导 onboarding — 校验、规范化与 profile_json 合并（对齐 docs/前端后端API文档.md）"""

from __future__ import annotations

from app.core.talent_mapping import resolve_talent_code, talent_primary_from_code

ALLOWED_ABILITIES: tuple[str, ...] = (
    "超脑阅读",
    "影像追忆",
    "扫描速记",
    "极速运算",
    "极速学习",
    "难题专练",
    "文科扫书",
    "理科扫书",
    "高效作业",
    "天赋绘画",
    "音乐灵感",
    "棋类专注",
)

PRIOR_DATA_FIELDS: tuple[str, ...] = (
    "firstDate",
    "totalCount",
    "lastTime",
    "lastResult",
    "note",
)


class OnboardingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _parse_int_or_none(raw) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _normalize_prior_training_data(
    raw: dict | None,
    prior_abilities: list[str],
) -> dict:
    if not prior_abilities:
        return {}
    out: dict = {}
    source = raw if isinstance(raw, dict) else {}
    for skill in prior_abilities:
        row = source.get(skill)
        if not isinstance(row, dict):
            out[skill] = {k: "" for k in PRIOR_DATA_FIELDS}
            continue
        out[skill] = {
            field: str(row.get(field) or "") if row.get(field) is not None else ""
            for field in PRIOR_DATA_FIELDS
        }
    return out


def normalize_onboarding(ob: dict | None, *, existing: dict | None = None) -> dict:
    """合并 existing + ob 并规范化字段（不抛校验错误）"""
    base = dict(existing or {})
    patch = dict(ob or {})
    merged = {**base, **patch}

    student_type = merged.get("student_type") or base.get("student_type") or "new"
    merged["student_type"] = student_type

    code = merged.get("self_reported_talent_code")
    name = merged.get("self_reported_talent")
    if name and str(name).strip() == "unknown":
        name = None
        merged["self_reported_talent"] = None
    if code and not name:
        fixed_name = talent_primary_from_code(int(code))
        if fixed_name:
            merged["self_reported_talent"] = fixed_name
            name = fixed_name
    if name and not code:
        fixed_code = resolve_talent_code(str(name).strip())
        if fixed_code:
            merged["self_reported_talent_code"] = fixed_code
            code = fixed_code

    if student_type == "returning":
        merged["talent_unknown"] = False
    elif merged.get("talent_unknown") and (code or name):
        merged["talent_unknown"] = False

    if "first_training_date" in merged:
        val = merged.get("first_training_date")
        merged["first_training_date"] = str(val).strip() if val else None

    if "total_training_sessions" in merged:
        merged["total_training_sessions"] = _parse_int_or_none(
            merged.get("total_training_sessions")
        )

    abilities_raw = merged.get("prior_abilities")
    if abilities_raw is not None:
        seen: set[str] = set()
        filtered: list[str] = []
        for item in abilities_raw if isinstance(abilities_raw, list) else []:
            skill = str(item).strip()
            if skill in ALLOWED_ABILITIES and skill not in seen:
                seen.add(skill)
                filtered.append(skill)
        merged["prior_abilities"] = filtered

    if "prior_training_data" in merged or merged.get("prior_abilities"):
        merged["prior_training_data"] = _normalize_prior_training_data(
            patch.get("prior_training_data") if "prior_training_data" in patch else merged.get("prior_training_data"),
            list(merged.get("prior_abilities") or []),
        )

    return merged


def validate_onboarding_merge(current_ob: dict | None, patch_ob: dict | None) -> None:
    """校验合并后的 onboarding（部分更新时结合已有数据）"""
    if not patch_ob:
        return
    current = dict(current_ob or {})
    normalized_patch = normalize_onboarding(patch_ob, existing=current)
    merged = normalize_onboarding(normalized_patch, existing=current)

    student_type = merged.get("student_type")
    if student_type != "returning":
        return

    talent_touched = any(
        key in patch_ob
        for key in (
            "self_reported_talent",
            "self_reported_talent_code",
            "talent_unknown",
            "student_type",
        )
    )
    if talent_touched:
        name = merged.get("self_reported_talent")
        code = merged.get("self_reported_talent_code")
        if merged.get("talent_unknown") or name == "unknown" or (not name and not code):
            raise OnboardingError("老学员必须选择五者天赋之一")

    if patch_ob.get("completed_at"):
        abilities = merged.get("prior_abilities") or []
        if not abilities:
            raise OnboardingError("老学员至少选择一项训练项目")


def merge_onboarding_into_profile(current_profile: dict | None, patch_profile: dict) -> dict:
    """深度合并 profile_json，onboarding.prior_training_data 按技能合并"""
    base = dict(current_profile or {})
    for key, val in patch_profile.items():
        if key == "onboarding" and isinstance(val, dict):
            current_ob = base.get("onboarding") if isinstance(base.get("onboarding"), dict) else {}
            merged_ob = normalize_onboarding(val, existing=current_ob)
            if isinstance(val.get("prior_training_data"), dict):
                base_ptd = dict(current_ob.get("prior_training_data") or {})
                base_ptd.update(val["prior_training_data"])
                merged_ob["prior_training_data"] = _normalize_prior_training_data(
                    base_ptd,
                    list(merged_ob.get("prior_abilities") or []),
                )
            base["onboarding"] = merged_ob
        elif isinstance(val, dict) and isinstance(base.get(key), dict):
            base[key] = {**base[key], **val}
        else:
            base[key] = val
    return base
