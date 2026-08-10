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
        db.execute(
            delete(TrainingItem).where(TrainingItem.plan_id.in_(plan_ids))
        )
        db.execute(delete(TrainingPlan).where(TrainingPlan.id.in_(plan_ids)))

    db.execute(delete(TrainingRecord).where(TrainingRecord.child_user_id == child_id))
    db.execute(delete(TrainingWindow).where(TrainingWindow.child_user_id == child_id))
    db.execute(delete(TalentAssessmentArchive).where(TalentAssessmentArchive.child_user_id == child_id))
    db.execute(delete(TalentAssessment).where(TalentAssessment.child_user_id == child_id))


def _suspend_student_account(db: Session, child: ChildUser) -> None:
    """移出生产环境：保留账号/训练数据/绑定，仅吊销 session。"""
    if child.role != auth_service.ROLE_STUDENT or not auth_service.is_account_active(child):
        return
    from app.services.session_service import revoke_all_sessions

    revoke_all_sessions(db, child.id)
    child.session_token = None
    auth_service.release_student_login_name(db, child)
    child.account_status = auth_service.ACCOUNT_REMOVED
    child.deleted_at = datetime.now(TZ)


def _suspend_parent_account(db: Session, parent: ChildUser) -> None:
    """移出生产环境：保留手机号/openid/孩子绑定与业务数据，仅吊销 session。"""
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
            _suspend_student_account(db, child)

    from app.services.session_service import revoke_all_sessions

    revoke_all_sessions(db, parent.id)
    parent.session_token = None
    parent.account_status = auth_service.ACCOUNT_REMOVED
    parent.deleted_at = datetime.now(TZ)


def _parent_out(db: Session, parent: ChildUser) -> dict:
    used = auth_service.count_parent_children(db, parent.id)
    return {
        "id": parent.id,
        "parent_phone": parent.parent_phone,
        "nickname": parent.nickname,
        "child_quota": auth_service.get_parent_quota_limit(parent),
        "children_count": used,
        "created_at": format_cst(parent.created_at),
        "account_status": parent.account_status or auth_service.ACCOUNT_ACTIVE,
        "display_phone": auth_service.effective_parent_phone(parent),
    }


def list_parents(db: Session, admin_id: int, *, q: str | None = None) -> list[dict]:
    _require_admin(db, admin_id)
    parents = db.scalars(
        select(ChildUser)
        .where(
            ChildUser.role == auth_service.ROLE_PARENT,
            ChildUser.account_status == auth_service.ACCOUNT_ACTIVE,
        )
        .order_by(ChildUser.id.desc())
    ).all()
    out = [_parent_out(db, p) for p in parents]
    if q:
        key = q.strip().lower()
        out = [
            p
            for p in out
            if key in (p["nickname"] or "").lower()
            or key in (p["display_phone"] or p["parent_phone"] or "")
        ]
    return out


def list_removed_parents(db: Session, admin_id: int, *, q: str | None = None) -> list[dict]:
    _require_admin(db, admin_id)
    rows = db.scalars(
        select(ChildUser)
        .where(
            ChildUser.role == auth_service.ROLE_PARENT,
            ChildUser.account_status.in_(
                (auth_service.ACCOUNT_REMOVED, auth_service.ACCOUNT_DELETED)
            ),
        )
        .order_by(ChildUser.deleted_at.desc(), ChildUser.id.desc())
    ).all()
    out = []
    for p in rows:
        item = _parent_out(db, p)
        item["removed_at"] = format_cst(p.deleted_at) if p.deleted_at else None
        out.append(item)
    if q:
        key = q.strip().lower()
        out = [
            p
            for p in out
            if key in (p["nickname"] or "").lower()
            or key in (p["display_phone"] or p["parent_phone"] or "")
        ]
    return out


def create_parent(
    db: Session,
    admin_id: int,
    *,
    parent_phone: str,
    nickname: str,
    password: str | None = None,
    child_quota: int = 5,
) -> dict:
    _require_admin(db, admin_id)
    from app.services.parent_reconcile_service import resolve_canonical_parent_for_login
    from app.services.sms_service import normalize_phone

    phone = normalize_phone(parent_phone)
    if resolve_canonical_parent_for_login(db, phone):
        raise HTTPException(409, "该手机号已有家长账号（含已移出），请使用恢复功能")
    user = auth_service.register_child(
        db,
        parent_phone=phone,
        nickname=nickname.strip(),
        password=password,
        role=auth_service.ROLE_PARENT,
        child_quota=child_quota,
    )
    return _parent_out(db, user)


def restore_parent(db: Session, admin_id: int, parent_id: int) -> dict:
    _require_admin(db, admin_id)
    parent = db.get(ChildUser, parent_id)
    if not parent or parent.role != auth_service.ROLE_PARENT:
        raise HTTPException(404, "家长不存在")
    if auth_service.is_account_active(parent):
        return _parent_out(db, parent)
    auth_service.restore_parent_account(db, parent)
    db.commit()
    db.refresh(parent)
    return _parent_out(db, parent)


def restore_parent_by_lookup(
    db: Session,
    admin_id: int,
    *,
    phone: str | None = None,
    nickname: str | None = None,
) -> dict:
    _require_admin(db, admin_id)
    if not phone and not nickname:
        raise HTTPException(400, "请提供手机号或昵称")
    parent = auth_service.find_parent_for_admin_restore(db, phone=phone, nickname=nickname)
    if not parent:
        raise HTTPException(404, "未找到已移出的家长账号")
    auth_service.restore_parent_account(db, parent)
    db.commit()
    db.refresh(parent)
    return _parent_out(db, parent)


def restore_child(db: Session, admin_id: int, child_id: int) -> dict:
    _require_admin(db, admin_id)
    child = db.get(ChildUser, child_id)
    if not child or child.role != auth_service.ROLE_STUDENT:
        raise HTTPException(404, "孩子不存在")
    if auth_service.is_account_active(child):
        return auth_service.child_summary(db, child)
    auth_service.restore_student_account(db, child)
    db.commit()
    db.refresh(child)
    return auth_service.child_summary(db, child)


def list_children(db: Session, admin_id: int, *, parent_id: int | None = None, q: str | None = None) -> list[dict]:
    _require_admin(db, admin_id)
    search = (q or "").strip()
    stmt = (
        select(ChildUser, ParentChildBind.parent_id)
        .outerjoin(ParentChildBind, ParentChildBind.child_id == ChildUser.id)
        .where(
            ChildUser.role == auth_service.ROLE_STUDENT,
            ChildUser.account_status == auth_service.ACCOUNT_ACTIVE,
        )
    )
    if parent_id is not None:
        from app.services.parent_reconcile_service import resolve_canonical_parent

        parent_row = db.get(ChildUser, parent_id)
        effective_id = parent_id
        if parent_row and parent_row.role == auth_service.ROLE_PARENT:
            canonical = resolve_canonical_parent(db, parent_row.parent_phone)
            if canonical:
                effective_id = canonical.id
        stmt = stmt.where(ParentChildBind.parent_id == effective_id)
    stmt = stmt.order_by(ChildUser.id.desc())
    rows = db.execute(stmt).all()
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
    if search:
        key = search.lower()
        out = [
            c
            for c in out
            if key in (c.get("nickname") or "").lower()
            or key in (c.get("login_name") or "").lower()
            or key in (c.get("parent_phone") or "")
            or key in (c.get("parent_nickname") or "").lower()
        ]
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
        from app.services.parent_reconcile_service import list_active_parents_by_phone

        for other in list_active_parents_by_phone(db, phone):
            if other.id != parent_id:
                raise HTTPException(409, "手机号已被使用")
        parent.parent_phone = phone
    if nickname is not None:
        parent.nickname = nickname.strip()
    if password is not None:
        from app.core.password_policy import validate_password_strength

        parent.password_hash = hash_password(validate_password_strength(password))
        from app.services.session_service import revoke_all_sessions

        revoke_all_sessions(db, parent.id)
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
        "account_status": parent.account_status,
        "display_phone": auth_service.effective_parent_phone(parent),
    }


def delete_parent(db: Session, admin_id: int, parent_id: int) -> None:
    _require_admin(db, admin_id)
    parent = db.get(ChildUser, parent_id)
    if not parent or parent.role != auth_service.ROLE_PARENT:
        raise HTTPException(404, "家长不存在")
    if not auth_service.is_account_active(parent):
        raise HTTPException(410, "账号已移出生产环境")
    _suspend_parent_account(db, parent)
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
        from app.core.password_policy import validate_password_strength

        child.password_hash = hash_password(validate_password_strength(password))
        from app.services.session_service import revoke_all_sessions

        revoke_all_sessions(db, child.id)
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
    if not auth_service.is_account_active(child):
        raise HTTPException(410, "账号已移出生产环境")
    _suspend_student_account(db, child)
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


def unbind_child(db: Session, admin_id: int, child_id: int) -> dict:
    _require_admin(db, admin_id)
    child = db.get(ChildUser, child_id)
    if (
        not child
        or child.role != auth_service.ROLE_STUDENT
        or not auth_service.is_account_active(child)
    ):
        raise HTTPException(404, "孩子不存在")
    db.execute(delete(ParentChildBind).where(ParentChildBind.child_id == child_id))
    child.parent_phone = ""
    pj = dict(child.profile_json or {})
    pj.pop("parentName", None)
    child.profile_json = pj
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(child, "profile_json")
    from app.services.session_service import revoke_all_sessions

    revoke_all_sessions(db, child_id)
    db.commit()
    return {
        "ok": True,
        "warning": "孩子已解绑，将无法登录，需重新绑定家长后方可恢复",
    }


def get_parent_detail(db: Session, admin_id: int, parent_id: int) -> dict:
    _require_admin(db, admin_id)
    parent = db.get(ChildUser, parent_id)
    if not parent or parent.role != auth_service.ROLE_PARENT:
        raise HTTPException(404, "家长不存在")

    from app.services.parent_reconcile_service import (
        duplicate_parent_summaries,
        find_unbound_students_by_phone,
        resolve_canonical_parent,
    )
    from app.services.session_service import list_user_sessions

    display_phone = auth_service.effective_parent_phone(parent)
    active = auth_service.is_account_active(parent)
    canonical = (resolve_canonical_parent(db, display_phone) or parent) if active else parent
    children = list_children(db, admin_id, parent_id=parent.id) if active else []
    if not active:
        child_ids = db.scalars(
            select(ParentChildBind.child_id).where(ParentChildBind.parent_id == parent.id)
        ).all()
        for cid in child_ids:
            ch = db.get(ChildUser, cid)
            if ch:
                children.append(auth_service.child_summary(db, ch))
    unbound = find_unbound_students_by_phone(db, display_phone) if active else []
    dupes = duplicate_parent_summaries(db, display_phone, exclude_id=parent.id) if active else []

    return {
        "id": parent.id,
        "parent_phone": display_phone,
        "nickname": parent.nickname,
        "child_quota": auth_service.get_parent_quota_limit(parent),
        "children_count": len(children),
        "created_at": format_cst(parent.created_at),
        "children": children,
        "active_sessions": list_user_sessions(db, parent.id) if active else [],
        "reconciled_count": 0,
        "pending_unbound_count": len(unbound),
        "unbound_children": [auth_service.child_summary(db, c) for c in unbound],
        "duplicate_parents": dupes,
        "canonical_parent_id": canonical.id,
        "is_duplicate_account": active and canonical.id != parent.id,
        "account_status": parent.account_status or auth_service.ACCOUNT_ACTIVE,
        "removed_at": format_cst(parent.deleted_at) if parent.deleted_at else None,
    }


def apply_parent_reconcile(db: Session, admin_id: int, parent_id: int) -> dict:
    """管理员确认后，将同手机号未绑定孩子挂到主家长名下。"""
    _require_admin(db, admin_id)
    parent = db.get(ChildUser, parent_id)
    if not parent or parent.role != auth_service.ROLE_PARENT or not auth_service.is_account_active(parent):
        raise HTTPException(404, "家长不存在")

    from app.services.parent_reconcile_service import reconcile_parent_children

    bound = reconcile_parent_children(db, parent_id)
    children = list_children(db, admin_id, parent_id=parent_id)
    return {"reconciled_count": bound, "children_count": len(children), "children": children}


def get_child_detail(db: Session, admin_id: int, child_id: int) -> dict:
    _require_admin(db, admin_id)
    child = db.get(ChildUser, child_id)
    if not child or child.role != auth_service.ROLE_STUDENT:
        raise HTTPException(404, "孩子不存在")

    active = auth_service.is_account_active(child)
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

    progress = get_training_progress(child) if active else {}
    summary = state_summary(progress) if active else {}
    history_items = get_checkin_history(db, child_id, limit=80) if active else []
    history_days = group_checkin_history_by_day(history_items) if active else []

    plans = []
    if active:
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
            "items": [
                {
                    "id": it.id,
                    "sort_order": it.sort_order,
                    "title": (it.title or "").strip() or "训练项",
                    "duration_min": it.duration_min,
                    "ability_type": it.ability_type,
                    "checkin_status": it.checkin_status or "pending",
                }
                for it in (p.items or [])
            ],
        }
        for p in plans
    ]

    pj = child.profile_json or {}
    base = auth_service.child_summary(db, child)
    login_name = auth_service.effective_student_login_name(child) or base.get("login_name")

    return {
        **base,
        "login_name": login_name,
        "account_status": child.account_status or auth_service.ACCOUNT_ACTIVE,
        "removed_at": format_cst(child.deleted_at) if child.deleted_at else None,
        "talent_display": pj.get("talent_display") or base.get("talent"),
        "overall_tier": summary.get("overall_tier") or (overall_tier(progress) if active else 1),
        "parent_id": parent.id if parent else None,
        "parent_phone": parent.parent_phone if parent else None,
        "parent_nickname": parent.nickname if parent else None,
        "created_at": format_cst(child.created_at),
        "training_progress": summary or None,
        "training_history_days": history_days[:30],
        "recent_plans": recent_plans,
        "active_sessions": list_user_sessions(db, child_id) if active else [],
    }
