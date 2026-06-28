"""天赋测评持久化"""

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.talent_mapping import resolve_talent_code, resolve_talent_tag
from app.db.models import ChildUser, TalentAssessment, TalentAssessmentArchive, TrainingRecord


def get_self_reported_talent_code(db: Session, child_user_id: int) -> int | None:
    """从注册引导页自选天赋中提取 talent_code（仅当用户明确选了天赋而非"不知道"）"""
    user = db.get(ChildUser, child_user_id)
    if not user or not user.profile_json:
        return None
    onboarding = user.profile_json.get("onboarding") if isinstance(user.profile_json, dict) else {}
    if not onboarding or onboarding.get("talent_unknown"):
        return None
    return onboarding.get("self_reported_talent_code")


def get_self_reported_talent_name(db: Session, child_user_id: int) -> str | None:
    """获取自选天赋名称"""
    user = db.get(ChildUser, child_user_id)
    if not user or not user.profile_json:
        return None
    onboarding = user.profile_json.get("onboarding") if isinstance(user.profile_json, dict) else {}
    if not onboarding or onboarding.get("talent_unknown"):
        return None
    return onboarding.get("self_reported_talent")


def has_training_records(db: Session, child_user_id: int) -> bool:
    """用户是否已有训练打卡记录"""
    return db.query(
        select(TrainingRecord).where(TrainingRecord.child_user_id == child_user_id).exists()
    ).scalar()

class AssessmentError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


TALENT_LOCK_MSG = "已有训练记录，天赋不可更改"


def resolve_talent_conflict(
    db: Session,
    child_user_id: int,
    *,
    action: str,  # "keep_old" | "use_new"
) -> dict:
    """用户选择保留旧天赋或采用新测评结果"""
    user = db.get(ChildUser, child_user_id)
    if not user or not user.profile_json:
        raise AssessmentError("用户不存在")
    profile = dict(user.profile_json)
    pending = profile.pop("pending_talent", None)
    if not pending:
        raise AssessmentError("没有待处理的天赋冲突", 404)

    if action == "use_new":
        # 采用新测评结果
        profile.update(
            {
                "talent_code": pending["talent_code"],
                "talent_tag": pending["talent_tag"],
                "talent_primary": pending["talent_primary"],
                "talent_source": "assessment",
                "latest_assessment_id": pending["assessment_id"],
            }
        )
        user.training_level = pending["talent_primary"]
        user.profile_json = profile
        db.commit()

        # 清除旧训练计划，按新天赋重建
        from app.services.training_service import refresh_today_plan_if_talent_changed
        refresh_today_plan_if_talent_changed(db, child_user_id)
        return {"action": "use_new", "talent_primary": pending["talent_primary"], "plans_reset": True}

    # keep_old — 保留当前天赋，清除 pending
    profile.pop("latest_assessment_id", None)
    user.profile_json = profile
    db.commit()
    return {"action": "keep_old", "talent_primary": profile.get("talent_primary"), "plans_reset": False}


def _assessment_snapshot(row: TalentAssessment) -> dict:
    return {
        "id": row.id,
        "child_user_id": row.child_user_id,
        "jnao_record_id": row.jnao_record_id,
        "answer_bitstring": row.answer_bitstring,
        "test_type": row.test_type,
        "talent_primary": row.talent_primary,
        "talent_tag": row.talent_tag,
        "talent_code": row.talent_code,
        "report_json": row.report_json,
        "assessed_at": row.assessed_at.isoformat() if row.assessed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def save_assessment(
    db: Session,
    *,
    child_user_id: int,
    jnao_record_id: str,
    answer_bitstring: str,
    test_type: int,
    report: dict,
) -> TalentAssessment:
    talent_primary = report.get("talent") or report.get("check_talent")
    talent_code = resolve_talent_code(talent_primary)
    talent_tag = resolve_talent_tag(talent_code)

    # 检测当前有效天赋（可能是自选或之前测评）
    user = db.get(ChildUser, child_user_id)
    current_profile = dict(user.profile_json or {}) if user else {}
    current_code = current_profile.get("talent_code")
    current_source = current_profile.get("talent_source", "")

    # 冲突检测：仅当 新测评结果 ≠ 自选天赋 时触发（JNAO 重测直接覆盖）
    talent_conflict = False
    talent_locked = False
    is_onboarding_source = current_source == "onboarding"
    if talent_code and current_code and talent_code != current_code:
        if has_training_records(db, child_user_id):
            # 有训练记录 → 锁定，不更新天赋
            talent_locked = True
        elif is_onboarding_source:
            # 自选天赋 vs JNAO 不同 → 标记冲突，等用户选择
            talent_conflict = True
        # else: JNAO 重测 → 直接覆盖，不触发冲突

    assessed_at = datetime.now(timezone.utc)
    if report.get("create_time"):
        try:
            raw = str(report["create_time"])
            if len(raw) > 10:
                assessed_at = datetime.strptime(raw[:16], "%Y-%m-%d %H:%M")
            else:
                assessed_at = datetime.strptime(raw[:10], "%Y-%m-%d").replace(
                    hour=assessed_at.hour,
                    minute=assessed_at.minute,
                )
        except ValueError:
            pass

    record = TalentAssessment(
        child_user_id=child_user_id,
        jnao_record_id=str(jnao_record_id),
        answer_bitstring=answer_bitstring,
        test_type=test_type,
        talent_primary=talent_primary,
        talent_tag=talent_tag,
        talent_code=talent_code,
        report_json=report,
        assessed_at=assessed_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    if not talent_locked and not talent_conflict:
        # 无冲突 → 正常同步天赋
        sync_child_user_talent(db, child_user_id)
    elif talent_conflict:
        # 有冲突 → 暂存冲突信息到 profile，等用户选择
        profile = dict(user.profile_json or {})
        profile["pending_talent"] = {
            "assessment_id": record.id,
            "talent_code": talent_code,
            "talent_tag": talent_tag,
            "talent_primary": talent_primary,
        }
        user.profile_json = profile
        db.commit()
    # talent_locked → 什么都不更新，仅存档测评

    from app.services.training_service import refresh_today_plan_if_talent_changed
    if not talent_locked and not talent_conflict:
        refresh_today_plan_if_talent_changed(db, child_user_id, assessment=record)
    db.refresh(record)

    # 在返回对象上附加冲突信息（非持久化字段）
    record._talent_conflict = talent_conflict
    record._talent_locked = talent_locked
    return record


def effective_talent_code(row: TalentAssessment | None) -> int | None:
    """与历史报告一致：优先库内 talent_code，否则从 talent_primary 解析
    迷者表示测评结果不明确，视为无有效天赋"""
    if not row:
        return None
    if row.talent_primary and row.talent_primary.strip() == "迷者":
        return None
    if row.talent_code:
        return row.talent_code
    return resolve_talent_code(row.talent_primary)


def has_valid_talent(row: TalentAssessment | None) -> bool:
    return effective_talent_code(row) is not None


def _backfill_talent_fields(db: Session, row: TalentAssessment) -> TalentAssessment:
    # 迷者：清除可能因旧版映射错误写入的 talent_code
    if row.talent_primary and row.talent_primary.strip() == "迷者":
        if row.talent_code is not None or row.talent_tag is not None:
            row.talent_code = None
            row.talent_tag = None
            db.commit()
            db.refresh(row)
        return row
    if row.talent_code:
        return row
    code = resolve_talent_code(row.talent_primary)
    if not code:
        return row
    row.talent_code = code
    row.talent_tag = resolve_talent_tag(code)
    db.commit()
    db.refresh(row)
    return row


def get_latest_assessment(db: Session, child_user_id: int) -> TalentAssessment | None:
    """取最新测评 — 与历史报告列表一致按 id 降序，并补全缺失的 talent_code"""
    row = db.scalar(
        select(TalentAssessment)
        .where(TalentAssessment.child_user_id == child_user_id)
        .order_by(TalentAssessment.id.desc())
        .limit(1)
    )
    if not row:
        return None
    return _backfill_talent_fields(db, row)


def sync_child_user_talent(db: Session, child_user_id: int) -> None:
    """将 child_user 上的天赋字段同步为最新测评结果
    优先级：JNAO 测评 > 注册引导自选天赋 > 无"""
    user = db.get(ChildUser, child_user_id)
    if not user:
        return
    latest = get_latest_assessment(db, child_user_id)
    profile = dict(user.profile_json or {})
    code = effective_talent_code(latest)

    if latest and code:
        # 有有效 JNAO 测评 → 使用测评结果
        user.training_level = latest.talent_primary
        profile.update(
            {
                "talent_code": code,
                "talent_tag": latest.talent_tag or resolve_talent_tag(code),
                "talent_primary": latest.talent_primary,
                "talent_source": "assessment",
                "latest_assessment_id": latest.id,
            }
        )
    else:
        # 无有效测评 → 尝试从注册引导页自选天赋提升
        self_code = get_self_reported_talent_code(db, child_user_id)
        self_name = get_self_reported_talent_name(db, child_user_id)
        if self_code:
            user.training_level = self_name
            profile.update(
                {
                    "talent_code": self_code,
                    "talent_tag": resolve_talent_tag(self_code),
                    "talent_primary": self_name,
                    "talent_source": "onboarding",
                }
            )
            # 清除旧的测评关联（如果有）
            profile.pop("latest_assessment_id", None)
        else:
            user.training_level = None
            for key in ("talent_code", "talent_tag", "talent_primary",
                        "talent_source", "latest_assessment_id"):
                profile.pop(key, None)
    user.profile_json = profile
    db.commit()


def list_assessments(db: Session, child_user_id: int, limit: int = 30) -> list[dict]:
    rows = db.scalars(
        select(TalentAssessment)
        .where(TalentAssessment.child_user_id == child_user_id)
        .order_by(TalentAssessment.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "talent": r.talent_primary,
            "talent_primary": r.talent_primary,
            "talent_tag": r.talent_tag,
            "create_time": (
                r.assessed_at.strftime("%Y-%m-%d %H:%M")
                if r.assessed_at
                else (r.report_json or {}).get("create_time")
            ),
            "assessed_at": r.assessed_at.isoformat() if r.assessed_at else None,
        }
        for r in rows
    ]


def get_assessment_by_id(db: Session, assessment_id: int, child_user_id: int) -> TalentAssessment | None:
    row = db.get(TalentAssessment, assessment_id)
    if not row or row.child_user_id != child_user_id:
        return None
    return row


def delete_assessment(db: Session, assessment_id: int, child_user_id: int) -> dict:
    """删除测评：先归档快照，再从主表删除"""
    row = get_assessment_by_id(db, assessment_id, child_user_id)
    if not row:
        raise AssessmentError("测评记录不存在", 404)

    db.add(
        TalentAssessmentArchive(
            original_id=row.id,
            child_user_id=row.child_user_id,
            snapshot_json=_assessment_snapshot(row),
            deleted_at=datetime.now(timezone.utc),
        )
    )
    db.delete(row)
    db.commit()
    sync_child_user_talent(db, child_user_id)
    from app.services.training_service import refresh_today_plan_if_talent_changed

    refresh_today_plan_if_talent_changed(db, child_user_id)
    return {"deleted": True, "assessment_id": assessment_id}
