"""家长—孩子绑定对账：修复未绑定孩子、重复家长账号导致的列表不一致"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ChildUser, ParentChildBind
from app.services import auth_service
from app.services.sms_service import normalize_phone


def list_active_parents_by_phone(db: Session, phone: str) -> list[ChildUser]:
    p = normalize_phone(phone)
    return list(
        db.scalars(
            select(ChildUser)
            .where(
                ChildUser.parent_phone == p,
                ChildUser.role == auth_service.ROLE_PARENT,
                ChildUser.account_status == auth_service.ACCOUNT_ACTIVE,
            )
            .order_by(ChildUser.id.asc())
        ).all()
    )


def resolve_canonical_parent(db: Session, phone: str) -> ChildUser | None:
    """同手机号多个家长时，优先：daka_member > 孩子最多 > id 最小。"""
    parents = list_active_parents_by_phone(db, phone)
    if not parents:
        return None
    if len(parents) == 1:
        return parents[0]

    from app.services.member_registry_service import find_daka_member_by_mobile

    dm = find_daka_member_by_mobile(db, phone)
    if dm:
        for p in parents:
            if p.id == dm.parent_id:
                return p

    def _child_count(pid: int) -> int:
        return auth_service.count_parent_children(db, pid)

    return max(parents, key=lambda p: (_child_count(p.id), -p.id))


def find_unbound_students_by_phone(db: Session, phone: str) -> list[ChildUser]:
    """parent_phone 匹配但尚无 parent_child_bind 的活跃学生。"""
    p = normalize_phone(phone)
    bound_ids = select(ParentChildBind.child_id)
    return list(
        db.scalars(
            select(ChildUser)
            .where(
                ChildUser.role == auth_service.ROLE_STUDENT,
                ChildUser.account_status == auth_service.ACCOUNT_ACTIVE,
                ChildUser.parent_phone == p,
                ChildUser.id.not_in(bound_ids),
            )
            .order_by(ChildUser.id.asc())
        ).all()
    )


def reconcile_parent_children(db: Session, parent_id: int) -> int:
    """将同手机号的未绑定孩子挂到该手机号的主家长名下；返回新绑定数量。"""
    parent = auth_service.get_child_user(db, parent_id)
    if not parent or parent.role != auth_service.ROLE_PARENT:
        return 0
    if not auth_service.is_account_active(parent):
        return 0

    canonical = resolve_canonical_parent(db, parent.parent_phone) or parent
    target_id = canonical.id

    bound = 0
    for child in find_unbound_students_by_phone(db, parent.parent_phone):
        if not auth_service.parent_can_add_child(db, canonical):
            break
        auth_service.bind_parent_child(db, target_id, child.id)
        pj = dict(child.profile_json or {})
        pj["parentName"] = canonical.nickname
        child.profile_json = pj
        bound += 1
    if bound:
        db.commit()
    return bound


def duplicate_parent_summaries(db: Session, phone: str, *, exclude_id: int | None = None) -> list[dict]:
    out = []
    for p in list_active_parents_by_phone(db, phone):
        if exclude_id is not None and p.id == exclude_id:
            continue
        out.append(
            {
                "id": p.id,
                "nickname": p.nickname,
                "children_count": auth_service.count_parent_children(db, p.id),
            }
        )
    return out
