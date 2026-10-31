"""管理员 API — 最高权限账号管理"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.deps import get_admin_user, get_db
from app.core.session_cookie import clear_session_cookie, maybe_strip_token, set_session_cookie
from app.schemas.admin import (
    AdminBindChildRequest,
    AdminChildListResponse,
    AdminChildOut,
    AdminCreateChildRequest,
    AdminCreateParentRequest,
    AdminLoginRequest,
    AdminParentListResponse,
    AdminParentOut,
    AdminRestoreByPhoneRequest,
    AdminUpdateChildRequest,
    AdminUpdateParentRequest,
    AdminPlatformConfigResponse,
    AdminUpdatePlatformConfigRequest,
    AdminParentDetailResponse,
    AdminChildDetailResponse,
    AdminReconcileResponse,
    AdminBlacklistResponse,
    AdminTalentQuotaRequest,
    AdminTalentQuotaBatchRequest,
    AdminTalentQuotaResponse,
    BlacklistEntryOut,
)
from app.schemas.auth import AuthResponse
from app.services import admin_service, auth_service
from app.services.blacklist_service import (
    check_auth_allowed,
    clear_auth_failures,
    record_auth_failure,
)
from app.services.sms_service import client_ip_from_request, device_id_from_request

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/login", response_model=AuthResponse)
def admin_login(req: AdminLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip_from_request(request)
    did = device_id_from_request(request) or ""
    check_auth_allowed(db, client_ip=ip, device_id=did)
    user = auth_service.login_admin_by_password(db, req.login_name, req.password)
    if not user:
        record_auth_failure(db, client_ip=ip, device_id=did)
        raise HTTPException(401, "账号或密码错误")
    clear_auth_failures(client_ip=ip, device_id=did)
    from app.services.session_service import issue_session

    issue_session(db, user)
    set_session_cookie(response, user.session_token or "", role=auth_service.ROLE_ADMIN)
    return AuthResponse(
        child_user_id=user.id,
        parent_phone=user.parent_phone,
        nickname=user.nickname,
        role=auth_service.ROLE_ADMIN,
        login_name=user.login_name,
        session_token=maybe_strip_token(user.session_token),
    )


@router.post("/logout")
def admin_logout(
    response: Response,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    from app.services.session_service import revoke_all_sessions

    revoke_all_sessions(db, admin_id)
    db.commit()
    clear_session_cookie(response, role=auth_service.ROLE_ADMIN)
    return {"ok": True}


@router.get("/parents", response_model=AdminParentListResponse)
def list_parents(
    q: str | None = Query(None, max_length=50),
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    items = admin_service.list_parents(db, admin_id, q=q)
    return AdminParentListResponse(parents=[AdminParentOut(**p) for p in items])


@router.get("/parents/removed", response_model=AdminParentListResponse)
def list_removed_parents(
    q: str | None = Query(None, max_length=50),
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    items = admin_service.list_removed_parents(db, admin_id, q=q)
    return AdminParentListResponse(parents=[AdminParentOut(**p) for p in items])


@router.post("/parents", response_model=AdminParentOut)
def create_parent(
    req: AdminCreateParentRequest,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    data = admin_service.create_parent(
        db,
        admin_id,
        parent_phone=req.parent_phone,
        nickname=req.nickname,
        password=req.password,
        child_quota=req.child_quota,
    )
    return AdminParentOut(**data)


@router.post("/parents/restore-by-phone", response_model=AdminParentOut)
def restore_parent_by_phone(
    req: AdminRestoreByPhoneRequest,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    data = admin_service.restore_parent_by_lookup(
        db, admin_id, phone=req.phone, nickname=req.nickname
    )
    return AdminParentOut(**data)


@router.post("/parents/{parent_id}/restore", response_model=AdminParentOut)
def restore_parent(
    parent_id: int,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    data = admin_service.restore_parent(db, admin_id, parent_id)
    return AdminParentOut(**data)


@router.put("/parents/{parent_id}", response_model=AdminParentOut)
def update_parent(
    parent_id: int,
    req: AdminUpdateParentRequest,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    data = admin_service.update_parent(
        db,
        admin_id,
        parent_id,
        nickname=req.nickname,
        parent_phone=req.parent_phone,
        password=req.password,
        child_quota=req.child_quota,
    )
    return AdminParentOut(**data)


@router.delete("/parents/{parent_id}")
def delete_parent(
    parent_id: int,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    admin_service.delete_parent(db, admin_id, parent_id)
    return {"ok": True}


@router.get("/children", response_model=AdminChildListResponse)
def list_children(
    parent_id: int | None = Query(None, ge=1),
    q: str | None = Query(None, max_length=50),
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    items = admin_service.list_children(db, admin_id, parent_id=parent_id, q=q)
    return AdminChildListResponse(children=[AdminChildOut(**c) for c in items])


@router.post("/children", response_model=AdminChildOut)
def create_child(
    req: AdminCreateChildRequest,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    data = admin_service.create_child_for_parent(
        db,
        admin_id,
        req.parent_id,
        login_name=req.login_name,
        nickname=req.nickname,
        password=req.password,
        grade=req.grade,
        age=req.age,
    )
    return AdminChildOut(**data)


@router.put("/children/{child_id}", response_model=AdminChildOut)
def update_child(
    child_id: int,
    req: AdminUpdateChildRequest,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    data = admin_service.update_child(
        db,
        admin_id,
        child_id,
        nickname=req.nickname,
        password=req.password,
        grade=req.grade,
        age=req.age,
        login_name=req.login_name,
    )
    return AdminChildOut(**data)


@router.delete("/children/{child_id}")
def delete_child(
    child_id: int,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    admin_service.delete_child(db, admin_id, child_id)
    return {"ok": True}


@router.post("/children/{child_id}/restore", response_model=AdminChildOut)
def restore_child(
    child_id: int,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    data = admin_service.restore_child(db, admin_id, child_id)
    return AdminChildOut(**data)


@router.post("/children/{child_id}/bind", response_model=AdminChildOut)
def bind_child(
    child_id: int,
    req: AdminBindChildRequest,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    data = admin_service.bind_child(db, admin_id, child_id, req.parent_id)
    return AdminChildOut(**data)


@router.delete("/children/{child_id}/bind")
def unbind_child(
    child_id: int,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    return admin_service.unbind_child(db, admin_id, child_id)


@router.get("/settings", response_model=AdminPlatformConfigResponse)
def get_settings(admin_id: int = Depends(get_admin_user), db: Session = Depends(get_db)):
    from app.services.platform_config import get_platform_config

    return AdminPlatformConfigResponse(**get_platform_config(db))


@router.put("/settings", response_model=AdminPlatformConfigResponse)
def update_settings(
    req: AdminUpdatePlatformConfigRequest,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    from app.services.platform_config import update_platform_config

    data = update_platform_config(
        db, admin_id, login_policy=req.login_policy.model_dump(exclude_none=True)
    )
    return AdminPlatformConfigResponse(**data)


@router.get("/parents/{parent_id}/detail", response_model=AdminParentDetailResponse)
def parent_detail(
    parent_id: int,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    return AdminParentDetailResponse(**admin_service.get_parent_detail(db, admin_id, parent_id))


@router.post("/parents/{parent_id}/reconcile", response_model=AdminReconcileResponse)
def reconcile_parent(
    parent_id: int,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    data = admin_service.apply_parent_reconcile(db, admin_id, parent_id)
    return AdminReconcileResponse(
        reconciled_count=data["reconciled_count"],
        children_count=data["children_count"],
        children=[AdminChildOut(**c) for c in data["children"]],
    )


@router.get("/children/{child_id}/detail", response_model=AdminChildDetailResponse)
def child_detail(
    child_id: int,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    return AdminChildDetailResponse(**admin_service.get_child_detail(db, admin_id, child_id))


@router.get("/blacklist", response_model=AdminBlacklistResponse)
def get_blacklist(admin_id: int = Depends(get_admin_user), db: Session = Depends(get_db)):
    from app.services.blacklist_service import list_blacklist

    data = list_blacklist(db)
    return AdminBlacklistResponse(
        ips=[BlacklistEntryOut(**r) for r in data.get("ips", [])],
        phones=[BlacklistEntryOut(**r) for r in data.get("phones", [])],
        devices=[BlacklistEntryOut(**r) for r in data.get("devices", [])],
    )


@router.delete("/blacklist/{kind}/{value}")
def remove_blacklist(
    kind: str,
    value: str,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    from app.services.blacklist_service import remove_blacklist_entry
    from urllib.parse import unquote

    if kind not in ("ip", "phone", "device"):
        raise HTTPException(400, "无效类型")
    ok = remove_blacklist_entry(db, kind, unquote(value))
    if not ok:
        raise HTTPException(404, "未找到该黑名单记录")
    return {"ok": True}


# ── 天赋测试配额管理 ──

@router.get("/children/{child_id}/talent-quota", response_model=AdminTalentQuotaResponse)
def get_child_talent_quota(
    child_id: int,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """查看孩子的天赋测试配额"""
    from app.db.models import ChildUser, TalentAssessment
    from sqlalchemy import func, select as sa_select

    user = db.get(ChildUser, child_id)
    if not user:
        raise HTTPException(404, "孩子不存在")
    profile = dict(user.profile_json or {})
    quota = profile.get("talent_test_quota", 2)
    used = db.scalar(
        sa_select(func.count()).select_from(TalentAssessment).where(
            TalentAssessment.child_user_id == child_id,
            TalentAssessment.talent_primary != "迷者",
            TalentAssessment.talent_code.isnot(None),
        )
    ) or 0
    return AdminTalentQuotaResponse(
        child_id=child_id,
        nickname=user.nickname or "",
        talent_test_quota=quota,
        valid_tests_used=used,
        remaining=max(0, quota - used),
    )


@router.put("/children/{child_id}/talent-quota", response_model=AdminTalentQuotaResponse)
def update_child_talent_quota(
    child_id: int,
    req: AdminTalentQuotaRequest,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """调整孩子的天赋测试次数（正数增加，负数减少，不低于已用次数或默认2）"""
    from app.db.models import ChildUser, TalentAssessment
    from sqlalchemy import func, select as sa_select

    user = db.get(ChildUser, child_id)
    if not user:
        raise HTTPException(404, "孩子不存在")
    profile = dict(user.profile_json or {})
    old_quota = profile.get("talent_test_quota", 2)
    used = db.scalar(
        sa_select(func.count()).select_from(TalentAssessment).where(
            TalentAssessment.child_user_id == child_id,
            TalentAssessment.talent_primary != "迷者",
            TalentAssessment.talent_code.isnot(None),
        )
    ) or 0
    floor = max(2, used)  # 最低不少于默认2次或已用次数
    new_quota = old_quota + req.add
    if new_quota < floor:
        raise HTTPException(400, f"不能低于 {floor} 次（已用 {used} 次，默认最低 2 次）")
    profile["talent_test_quota"] = new_quota
    user.profile_json = profile
    db.commit()
    return AdminTalentQuotaResponse(
        child_id=child_id,
        nickname=user.nickname or "",
        talent_test_quota=new_quota,
        valid_tests_used=used,
        remaining=max(0, new_quota - used),
    )


@router.put("/children/talent-quota/batch")
def batch_update_talent_quota(
    req: AdminTalentQuotaBatchRequest,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """批量为孩子增加天赋测试次数"""
    from app.db.models import ChildUser

    updated = 0
    for cid in req.child_ids:
        user = db.get(ChildUser, cid)
        if not user:
            continue
        profile = dict(user.profile_json or {})
        old_quota = profile.get("talent_test_quota", 2)
        profile["talent_test_quota"] = old_quota + req.add
        user.profile_json = profile
        updated += 1
    db.commit()
    return {"ok": True, "updated": updated, "add": req.add}


@router.get("/children/{child_id}/talent-assessments")
def get_child_assessments(
    child_id: int,
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """查看孩子的天赋测评历史"""
    from app.db.models import TalentAssessment
    from app.services.datetime_fmt import format_cst

    rows = db.scalars(
        __import__("sqlalchemy").select(TalentAssessment)
        .where(TalentAssessment.child_user_id == child_id)
        .order_by(TalentAssessment.id.desc())
    ).all()
    return [
        {
            "id": r.id,
            "talent_primary": r.talent_primary or "迷者",
            "talent_tag": r.talent_tag,
            "is_valid": r.talent_primary != "迷者" and r.talent_code is not None,
            "assessed_at": format_cst(r.assessed_at) if r.assessed_at else None,
            "created_at": format_cst(r.created_at),
        }
        for r in rows
    ]
