"""管理员 API — 最高权限账号管理"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import get_admin_user, get_db
from app.schemas.admin import (
    AdminBindChildRequest,
    AdminChildListResponse,
    AdminChildOut,
    AdminCreateChildRequest,
    AdminLoginRequest,
    AdminParentListResponse,
    AdminParentOut,
    AdminUpdateChildRequest,
    AdminUpdateParentRequest,
    AdminPlatformConfigResponse,
    AdminUpdatePlatformConfigRequest,
    AdminParentDetailResponse,
    AdminChildDetailResponse,
    AdminReconcileResponse,
    AdminBlacklistResponse,
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
def admin_login(req: AdminLoginRequest, request: Request, db: Session = Depends(get_db)):
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
    return AuthResponse(
        child_user_id=user.id,
        parent_phone=user.parent_phone,
        nickname=user.nickname,
        role=auth_service.ROLE_ADMIN,
        login_name=user.login_name,
        session_token=user.session_token,
    )


@router.get("/parents", response_model=AdminParentListResponse)
def list_parents(admin_id: int = Depends(get_admin_user), db: Session = Depends(get_db)):
    items = admin_service.list_parents(db, admin_id)
    return AdminParentListResponse(parents=[AdminParentOut(**p) for p in items])


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
    admin_id: int = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    items = admin_service.list_children(db, admin_id, parent_id=parent_id)
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
