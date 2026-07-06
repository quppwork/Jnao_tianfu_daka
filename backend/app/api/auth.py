"""用户注册 / 登录"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.security import is_legacy_register_enabled
from app.schemas.auth import (
    AuthResponse,
    CaptchaResponse,
    LoginRequest,
    RegisterRequest,
    SmsLoginRequest,
    SmsRegisterRequest,
    SmsSendRequest,
    SmsSendResponse,
)
from app.services import auth_service
from app.services.blacklist_service import (
    check_auth_allowed,
    clear_auth_failures,
    record_auth_failure,
)
from app.services.captcha_service import create_captcha
from app.services.parent_profile_service import (
    login_parent_by_sms,
    parent_profile_status,
    register_parent_by_sms,
)
from app.services.sms_service import (
    SCENE_LOGIN,
    SCENE_REGISTER,
    client_ip_from_request,
    device_id_from_request,
    send_sms_code,
    verify_sms_code,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_ctx(request: Request, device_id: str | None = None) -> tuple[str, str]:
    ip = client_ip_from_request(request)
    did = (device_id or device_id_from_request(request) or "").strip()
    return ip, did


def _to_response(user) -> AuthResponse:
    complete, missing = (True, [])
    if (user.role or auth_service.ROLE_STUDENT) == auth_service.ROLE_PARENT:
        complete, missing = parent_profile_status(user)
    return AuthResponse(
        child_user_id=user.id,
        parent_phone=user.parent_phone,
        nickname=user.nickname,
        role=user.role or auth_service.ROLE_STUDENT,
        login_name=user.login_name,
        session_token=user.session_token,
        profile_complete=complete,
        missing_fields=missing,
    )


def _issue_and_respond(db: Session, user) -> AuthResponse:
    from app.services.session_service import issue_session

    issue_session(db, user)
    db.refresh(user)
    return _to_response(user)


@router.get("/captcha", response_model=CaptchaResponse)
def get_captcha():
    return CaptchaResponse(**create_captcha())


@router.get("/parent/phone-check")
def parent_phone_check(phone: str = Query(..., min_length=11), db: Session = Depends(get_db)):
    p = phone.strip()
    exists = auth_service.find_parent_by_phone(db, p) is not None
    return {"registered": exists}


@router.post("/sms/send", response_model=SmsSendResponse)
def sms_send(req: SmsSendRequest, request: Request, db: Session = Depends(get_db)):
    ip, did = _auth_ctx(request, req.device_id)
    data = send_sms_code(
        db,
        phone=req.phone,
        scene=req.scene,
        client_ip=ip,
        device_id=did,
        captcha_id=req.captcha_id,
        captcha_code=req.captcha_code,
    )
    return SmsSendResponse(**data)


@router.post("/sms/login", response_model=AuthResponse)
def sms_login(req: SmsLoginRequest, request: Request, db: Session = Depends(get_db)):
    ip, did = _auth_ctx(request, req.device_id)
    check_auth_allowed(db, client_ip=ip, phone=req.phone.strip(), device_id=did)
    try:
        verify_sms_code(req.phone, req.sms_code, SCENE_LOGIN)
        user = login_parent_by_sms(db, phone=req.phone.strip())
        clear_auth_failures(client_ip=ip, phone=req.phone.strip(), device_id=did)
        return _issue_and_respond(db, user)
    except HTTPException as e:
        if e.status_code in (400, 401, 404, 429):
            record_auth_failure(db, client_ip=ip, phone=req.phone.strip(), device_id=did)
        raise


@router.post("/sms/register", response_model=AuthResponse)
def sms_register(req: SmsRegisterRequest, request: Request, db: Session = Depends(get_db)):
    ip, did = _auth_ctx(request, req.device_id)
    check_auth_allowed(db, client_ip=ip, phone=req.phone.strip(), device_id=did)
    try:
        verify_sms_code(req.phone, req.sms_code, SCENE_REGISTER)
        user = register_parent_by_sms(
            db,
            phone=req.phone.strip(),
            nickname=req.nickname,
            real_name=req.real_name,
            password=req.password,
        )
        clear_auth_failures(client_ip=ip, phone=req.phone.strip(), device_id=did)
        return _issue_and_respond(db, user)
    except HTTPException as e:
        if e.status_code in (400, 409, 429):
            record_auth_failure(db, client_ip=ip, phone=req.phone.strip(), device_id=did)
        raise


@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    role = req.role or auth_service.ROLE_STUDENT

    if role == auth_service.ROLE_PARENT:
        raise HTTPException(400, "家长请使用验证码注册")

    if not is_legacy_register_enabled():
        raise HTTPException(
            403,
            "请由家长创建孩子账号或使用账号密码登录",
        )

    existing = auth_service.find_child_by_phone(db, req.parent_phone, req.nickname)
    if existing:
        raise HTTPException(409, "该账号已注册，请使用账号密码登录")

    user = auth_service.register_child(
        db,
        parent_phone=req.parent_phone,
        nickname=req.nickname,
        jnao_uid=req.jnao_uid,
        password=req.password,
        login_name=req.login_name,
        role=auth_service.ROLE_STUDENT,
    )
    return _issue_and_respond(db, user)


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip, did = _auth_ctx(request, None)

    if req.role == auth_service.ROLE_PARENT or (
        req.parent_phone and req.password and not req.login_name and not req.nickname
    ):
        if not req.parent_phone or not req.password:
            raise HTTPException(400, "请输入手机号和密码")
        check_auth_allowed(db, client_ip=ip, phone=req.parent_phone.strip(), device_id=did)
        user = auth_service.login_parent_by_password(db, req.parent_phone, req.password)
        if not user:
            record_auth_failure(db, client_ip=ip, phone=req.parent_phone.strip(), device_id=did)
            raise HTTPException(401, "手机号或密码错误")
        clear_auth_failures(client_ip=ip, phone=req.parent_phone.strip(), device_id=did)
        return _issue_and_respond(db, user)

    if req.login_name and req.password:
        from app.core.password import verify_password

        user = auth_service.find_user_by_login_name(db, req.login_name)
        if not user or not verify_password(req.password, user.password_hash):
            record_auth_failure(db, client_ip=ip, device_id=did)
            raise HTTPException(401, "账号或密码错误")
        if not auth_service.has_active_parent_bind(db, user.id):
            raise HTTPException(403, "账号未绑定家长，请联系管理员")
        clear_auth_failures(client_ip=ip, device_id=did)
        return _issue_and_respond(db, user)

    raise HTTPException(400, "请提供有效的登录信息")
