"""管理员 — 家长/孩子管理；删除为软删除（账户归档，释放占用）"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.password import hash_password
from app.db.models import (
    ChildUser,
    GuideMessage,
    GuideSession,
    ParentChildBind,
    QaMessage,
    QaSession,
    TalentAssessment,
    TalentAssessmentArchive,
    TrainingItem,
    TrainingPlan,
    TrainingRecord,
    TrainingWindow,
)
from app.services import auth_service
from app.services.datetime_fmt import format_cst

TZ = timezone(timedelta(hours=8))


def _require_admin(db: Session, admin_id: int) -> ChildUser:
    user = db.get(ChildUser, admin_id)
    if not user or user.role != auth_service.ROLE_ADMIN:
        raise HTTPException(403, "需要管理员权限")
    if not auth_service.is_account_active(user):
        raise HTTPException(401, "管理员账号已停用")
    return user


def _purge_student_operational_data(db: Session, child_id: int) -> None:
    """清除训练/测评/答疑等业务数据，保留 child_user 归档行"""
    session_ids = list(
        db.scalars(select(QaSession.id).where(QaSession.child_user_id == child_id)).all()
    )
    if session_ids:
        db.execute(delete(QaMessage).where(QaMessage.session_id.in_(session_ids)))
        db.execute(delete(QaSession).where(QaSession.id.in_(session_ids)))

    guide_ids = list(
        db.scalars(select(GuideSession.id).where(GuideSession.child_user_id == child_id)).all()
    )
    if guide_ids:
        db.execute(delete(GuideMessage).where(GuideMessage.session_id.in_(guide_ids)))
        db.execute(delete(GuideSession).where(GuideSession.id.in_(guide_ids)))

    plan_ids = list(
        db.scalars(select(TrainingPlan.id).where(TrainingPlan.child_user_id == child_id)).all()
    )
    if plan_ids:
        db.execute(delete(TrainingRecord).where(TrainingRecord.plan_id.in_(plan_ids)))
        db.execute(delete(TrainingItem).where(TrainingItem.plan_id.in_(plan_ids)))
        db.execute(delete(TrainingPlan).where(TrainingPlan.id.in_(plan_ids)))

    db.execute(delete(TrainingRecord).where(TrainingRecord.child_user_id == child_id))
    db.execute(delete(TrainingWindow).where(TrainingWindow.child_user_id == child_id))
    db.execute(delete(TalentAssessmentArchive).where(TalentAssessmentArchive.child_user_id == child_id))
    db.execute(delete(TalentAssessment).where(TalentAssessment.child_user_id == child_id))


def _archive_student_account(db: Session, child: ChildUser) -> None:
    """软删除孩子：归档账户信息，释放 login_name，不参与生产逻辑"""
    if child.role != auth_service.ROLE_STUDENT or not auth_service.is_account_active(child):
        return
    _purge_student_operational_data(db, child.id)
    db.execute(delete(ParentChildBind).where(ParentChildBind.child_id == child.id))

    pj = dict(child.profile_json or {})
    if child.login_name and not str(child.login_name).startswith("__deleted_"):
        pj["archived_login_name"] = child.login_name
        child.login_name = f"__deleted_{child.id}"
    pj["archived_parent_phone"] = child.parent_phone
    pj["archived_nickname"] = child.nickname
    child.profile_json = pj
    child.password_hash = None
    from app.services.session_service import revoke_all_sessions

    revoke_all_sessions(db, child.id)
    child.session_token = None
    child.training_level = None
    child.account_status = auth_service.ACCOUNT_DELETED
    child.deleted_at = datetime.now(TZ)


def _archive_parent_account(db: Session, parent: ChildUser) -> None:
    """软删除家长：先归档名下孩子，再归档家长并释放手机号"""
    if parent.role != auth_service.ROLE_PARENT or not auth_service.is_account_active(parent):
        return
    child_ids = list(
        db.scalars(
            select(ChildUser.id)
            .join(ParentChildBind, ParentChildBind.child_id == ChildUser.id)
            .where(
                ParentChildBind.parent_id == parent.id,
                ChildUser.account_status == auth_service.ACCOUNT_ACTIVE,
            )
        ).all()
    )
    for cid in child_ids:
        child = db.get(ChildUser, cid)
        if child:
            _archive_student_account(db, child)

    db.execute(delete(ParentChildBind).where(ParentChildBind.parent_id == parent.id))

    pj = dict(parent.profile_json or {})
    pj["archived_parent_phone"] = parent.parent_phone
    pj["archived_nickname"] = parent.nickname
    parent.profile_json = pj
    parent.parent_phone = f"__deleted_parent_{parent.id}"
    parent.password_hash = None
    from app.services.session_service import revoke_all_sessions

    revoke_all_sessions(db, parent.id)
    parent.session_token = None
    parent.account_status = auth_service.ACCOUNT_DELETED
    parent.deleted_at = datetime.now(TZ)


def list_parents(db: Session, admin_id: int) -> list[dict]:
    _require_admin(db, admin_id)
    parents = db.scalars(
        select(ChildUser)
        .where(
            ChildUser.role == auth_service.ROLE_PARENT,
            ChildUser.account_status == auth_service.ACCOUNT_ACTIVE,
        )
        .order_by(ChildUser.id.desc())
    ).all()
    out = []
    for p in parents:
        used = auth_service.count_parent_children(db, p.id)
        out.append({
            "id": p.id,
            "parent_phone": p.parent_phone,
            "nickname": p.nickname,
            "child_quota": auth_service.get_parent_quota_limit(p),
            "children_count": used,
            "created_at": format_cst(p.created_at),
        })
    return out


def list_children(db: Session, admin_id: int, *, parent_id: int | None = None) -> list[dict]:
    _require_admin(db, admin_id)
    q = (
        select(ChildUser, ParentChildBind.parent_id)
        .outerjoin(ParentChildBind, ParentChildBind.child_id == ChildUser.id)
        .where(
            ChildUser.role == auth_service.ROLE_STUDENT,
            ChildUser.account_status == auth_service.ACCOUNT_ACTIVE,
        )
    )
    if parent_id is not None:
        q = q.where(ParentChildBind.parent_id == parent_id)
    q = q.order_by(ChildUser.id.desc())
    rows = db.execute(q).all()
    seen: set[int] = set()
    out = []
    for child, pid in rows:
        if child.id in seen:
            continue
        seen.add(child.id)
        parent = db.get(ChildUser, pid) if pid else None
        if parent and not auth_service.is_account_active(parent):
            parent = None
            pid = None
        summary = auth_service.child_summary(db, child)
        summary["parent_id"] = pid
        summary["parent_phone"] = parent.parent_phone if parent else None
        summary["parent_nickname"] = parent.nickname if parent else None
        out.append(summary)
    return out


def update_parent(
    db: Session,
    admin_id: int,
    parent_id: int,
    *,
    nickname: str | None = None,
    parent_phone: str | None = None,
    password: str | None = None,
    child_quota: int | None = None,
) -> dict:
    _require_admin(db, admin_id)
    parent = db.get(ChildUser, parent_id)
    if not parent or parent.role != auth_service.ROLE_PARENT or not auth_service.is_account_active(parent):
        raise HTTPException(404, "家长不存在")
    if parent_phone is not None:
        phone = parent_phone.strip()
        other = auth_service.find_parent_by_phone(db, phone)
        if other and other.id != parent_id:
            raise HTTPException(409, "手机号已被使用")
        parent.parent_phone = phone
    if nickname is not None:
        parent.nickname = nickname.strip()
    if password is not None:
        parent.password_hash = hash_password(password)
    if child_quota is not None:
        if child_quota < 0:
            raise HTTPException(400, "名额不能为负数")
        parent.child_quota = child_quota
    db.commit()
    db.refresh(parent)
    used = auth_service.count_parent_children(db, parent.id)
    return {
        "id": parent.id,
        "parent_phone": parent.parent_phone,
        "nickname": parent.nickname,
        "child_quota": auth_service.get_parent_quota_limit(parent),
        "children_count": used,
    }


def delete_parent(db: Session, admin_id: int, parent_id: int) -> None:
    _require_admin(db, admin_id)
    parent = db.get(ChildUser, parent_id)
    if not parent or parent.role != auth_service.ROLE_PARENT:
        raise HTTPException(404, "家长不存在")
    _archive_parent_account(db, parent)
    db.commit()


def create_child_for_parent(
    db: Session,
    admin_id: int,
    parent_id: int,
    *,
    login_name: str,
    nickname: str,
    password: str,
    grade: str | None = None,
    age: int | None = None,
) -> dict:
    _require_admin(db, admin_id)
    parent = db.get(ChildUser, parent_id)
    if not parent or parent.role != auth_service.ROLE_PARENT or not auth_service.is_account_active(parent):
        raise HTTPException(404, "家长不存在")
    from app.services import parent_service

    child = parent_service.create_child(
        db,
        parent_id,
        login_name=login_name,
        nickname=nickname,
        password=password,
        grade=grade,
        age=age,
    )
    return auth_service.child_summary(db, child)


def update_child(
    db: Session,
    admin_id: int,
    child_id: int,
    *,
    nickname: str | None = None,
    password: str | None = None,
    grade: str | None = None,
    age: int | None = None,
    login_name: str | None = None,
) -> dict:
    _require_admin(db, admin_id)
    child = db.get(ChildUser, child_id)
    if not child or child.role != auth_service.ROLE_STUDENT or not auth_service.is_account_active(child):
        raise HTTPException(404, "孩子不存在")
    if login_name is not None:
        ln = login_name.strip()
        other = auth_service.find_user_by_login_name(db, ln)
        if other and other.id != child_id:
            raise HTTPException(409, "账号已被使用")
        child.login_name = ln
    if nickname is not None:
        child.nickname = nickname.strip()
    if password is not None:
        child.password_hash = hash_password(password)
    pj = dict(child.profile_json or {})
    learner = dict(pj.get("learner") or {})
    if grade is not None:
        learner["grade"] = grade
        pj["grade"] = grade
    if age is not None:
        learner["age"] = age
        pj["age"] = age
    if learner:
        pj["learner"] = learner
    child.profile_json = pj
    db.commit()
    db.refresh(child)
    return auth_service.child_summary(db, child)


def delete_child(db: Session, admin_id: int, child_id: int) -> None:
    _require_admin(db, admin_id)
    child = db.get(ChildUser, child_id)
    if not child or child.role != auth_service.ROLE_STUDENT:
        raise HTTPException(404, "孩子不存在")
    _archive_student_account(db, child)
    db.commit()


def bind_child(db: Session, admin_id: int, child_id: int, parent_id: int) -> dict:
    _require_admin(db, admin_id)
    child = db.get(ChildUser, child_id)
    parent = db.get(ChildUser, parent_id)
    if not child or child.role != auth_service.ROLE_STUDENT or not auth_service.is_account_active(child):
        raise HTTPException(404, "孩子不存在")
    if not parent or parent.role != auth_service.ROLE_PARENT or not auth_service.is_account_active(parent):
        raise HTTPException(404, "家长不存在")
    existing = db.scalar(
        select(ParentChildBind).where(ParentChildBind.child_id == child_id)
    )
    if existing and existing.parent_id != parent_id:
        raise HTTPException(409, "孩子已绑定其他家长，请先解绑")
    if not auth_service.parent_can_add_child(db, parent) and not existing:
        raise HTTPException(403, "家长名额已满")
    auth_service.bind_parent_child(db, parent_id, child_id)
    child.parent_phone = parent.parent_phone
    pj = dict(child.profile_json or {})
    pj["parentName"] = parent.nickname
    child.profile_json = pj
    db.commit()
    db.refresh(child)
    summary = auth_service.child_summary(db, child)
    summary["parent_id"] = parent_id
    summary["parent_phone"] = parent.parent_phone
    summary["parent_nickname"] = parent.nickname
    return summary


def unbind_child(db: Session, admin_id: int, child_id: int) -> None:
    _require_admin(db, admin_id)
    child = db.get(ChildUser, child_id)
    if not child or not auth_service.is_account_active(child):
        raise HTTPException(404, "孩子不存在")
    db.execute(delete(ParentChildBind).where(ParentChildBind.child_id == child_id))
    from app.services.session_service import revoke_all_sessions

    revoke_all_sessions(db, child_id)
    db.commit()


def get_parent_detail(db: Session, admin_id: int, parent_id: int) -> dict:
    _require_admin(db, admin_id)
    parent = db.get(ChildUser, parent_id)
    if not parent or parent.role != auth_service.ROLE_PARENT or not auth_service.is_account_active(parent):
        raise HTTPException(404, "家长不存在")
    children = list_children(db, admin_id, parent_id=parent_id)
    from app.services.session_service import list_user_sessions

    return {
        "id": parent.id,
        "parent_phone": parent.parent_phone,
        "nickname": parent.nickname,
        "child_quota": auth_service.get_parent_quota_limit(parent),
        "children_count": len(children),
        "created_at": format_cst(parent.created_at),
        "children": children,
        "active_sessions": list_user_sessions(db, parent.id),
    }


def get_child_detail(db: Session, admin_id: int, child_id: int) -> dict:
    _require_admin(db, admin_id)
    child = db.get(ChildUser, child_id)
    if not child or child.role != auth_service.ROLE_STUDENT or not auth_service.is_account_active(child):
        raise HTTPException(404, "孩子不存在")

    from app.services.child_training_state import get_training_progress, overall_tier, state_summary
    from app.services.session_service import list_user_sessions
    from app.services.training_service import (
        get_checkin_history,
        group_checkin_history_by_day,
    )
    from sqlalchemy import select
    from app.db.models import TrainingPlan

    bind = db.scalar(select(ParentChildBind).where(ParentChildBind.child_id == child_id))
    parent = db.get(ChildUser, bind.parent_id) if bind else None
    if parent and not auth_service.is_account_active(parent):
        parent = None

    progress = get_training_progress(child)
    summary = state_summary(progress)
    history_items = get_checkin_history(db, child_id, limit=80)
    history_days = group_checkin_history_by_day(history_items)

    plans = db.scalars(
        select(TrainingPlan)
        .where(TrainingPlan.child_user_id == child_id)
        .order_by(TrainingPlan.plan_date.desc())
        .limit(15)
    ).all()
    recent_plans = [
        {
            "plan_id": p.id,
            "plan_date": p.plan_date.isoformat() if p.plan_date else None,
            "status": p.status,
            "planned_minutes": p.planned_minutes,
            "item_count": len(p.items),
        }
        for p in plans
    ]

    pj = child.profile_json or {}
    base = auth_service.child_summary(db, child)

    return {
        **base,
        "talent_display": pj.get("talent_display") or base.get("talent"),
        "overall_tier": summary.get("overall_tier") or overall_tier(progress),
        "parent_id": parent.id if parent else None,
        "parent_phone": parent.parent_phone if parent else None,
        "parent_nickname": parent.nickname if parent else None,
        "created_at": format_cst(child.created_at),
        "training_progress": summary,
        "training_history_days": history_days[:30],
        "recent_plans": recent_plans,
        "active_sessions": list_user_sessions(db, child_id),
    }
