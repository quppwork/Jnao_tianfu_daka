"""用户注册 / 登录"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_user, get_db
from app.core.security import is_legacy_register_enabled
from app.schemas.auth import (
    AuthResponse,
    CaptchaResponse,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    SmsLoginRequest,
    SmsRegisterRequest,
    SmsSendRequest,
    SmsSendResponse,
    WechatBindPhoneRequest,
    WechatConfigResponse,
    WechatExternalBindRequest,
    WechatOAuthUrlResponse,
    WechatSendBindSmsRequest,
    PhoneCheckRequest,
)
from app.services import auth_service
from app.services.blacklist_service import (
    check_auth_allowed,
    clear_auth_failures,
    record_auth_failure,
)
from app.services.captcha_service import create_captcha, verify_captcha
from app.services.parent_profile_service import (
    get_login_channel,
    login_parent_by_sms,
    parent_account_ready,
    parent_next_step,
    parent_profile_status,
    parent_wechat_missing_fields,
    register_parent_by_sms,
    LOGIN_CHANNEL_WECHAT,
)
from app.services.sms_service import (
    SCENE_BIND,
    SCENE_LOGIN,
    SCENE_REGISTER,
    client_ip_from_request,
    device_id_from_request,
    send_sms_code,
    verify_sms_code,
)
from app.services.wechat_auth_service import (
    build_oauth_url,
    build_external_bind_mobile_url,
    bind_mobile_return_url,
    complete_bind_phone,
    complete_external_bind_phone,
    consume_oauth_state,
    consume_login_exchange_ticket,
    create_bind_ticket,
    create_login_exchange_ticket,
    frontend_login_url,
    frontend_wechat_error_url,
    lookup_member_for_oauth,
    finalize_wechat_login_user,
    resolve_wechat_login,
    assert_bind_ticket_sms_allowed,
    use_external_bind_mobile,
    wechat_app_id,
    wechat_configured,
    exchange_code_for_openid,
    get_bind_ticket,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("jnao")


def _auth_ctx(request: Request, device_id: str | None = None) -> tuple[str, str]:
    ip = client_ip_from_request(request)
    did = (device_id or device_id_from_request(request) or "").strip()
    return ip, did


def _to_response(
    user,
    *,
    bind_ticket: str | None = None,
    db: Session | None = None,
) -> AuthResponse:
    from app.core.session_cookie import maybe_strip_token
    from app.services.parent_profile_service import parent_auth_flags

    complete, missing = (True, [])
    channel = "standard"
    gate_passed = True
    ready = True
    step = "home"
    if (user.role or auth_service.ROLE_STUDENT) == auth_service.ROLE_PARENT:
        channel = get_login_channel(user)
        if channel == LOGIN_CHANNEL_WECHAT:
            missing = parent_wechat_missing_fields(user)
            complete = len(missing) == 0
        else:
            complete, missing = parent_profile_status(user)
        if db is not None:
            gate_passed, ready, step = parent_auth_flags(db, user)
        else:
            ready = parent_account_ready(user) if channel == LOGIN_CHANNEL_WECHAT else complete
            step = parent_next_step(user) if channel == LOGIN_CHANNEL_WECHAT else (
                "home" if complete else "complete-profile"
            )
    return AuthResponse(
        child_user_id=user.id,
        parent_phone=user.parent_phone,
        nickname=user.nickname,
        role=user.role or auth_service.ROLE_STUDENT,
        login_name=user.login_name,
        session_token=maybe_strip_token(user.session_token),
        profile_complete=complete,
        missing_fields=missing,
        login_channel=channel,
        account_ready=ready,
        next_step=step,
        gate_passed=gate_passed,
        bind_ticket=bind_ticket,
    )


def _issue_and_respond(
    db: Session,
    user,
    response: Response,
    *,
    bind_ticket: str | None = None,
) -> AuthResponse:
    from app.core.session_cookie import set_session_cookie
    from app.services.session_service import issue_session

    issue_session(db, user)
    db.refresh(user)
    role = user.role or auth_service.ROLE_STUDENT
    set_session_cookie(response, user.session_token or "", role=role)
    return _to_response(
        user,
        bind_ticket=bind_ticket,
        db=db,
    )


def _attach_cookie_for_user(response: Response, user) -> AuthResponse:
    from app.core.session_cookie import set_session_cookie

    role = user.role or auth_service.ROLE_STUDENT
    set_session_cookie(response, user.session_token or "", role=role)
    return _to_response(user)


@router.get("/captcha", response_model=CaptchaResponse)
def get_captcha(request: Request):
    ip, _ = _auth_ctx(request, None)
    return CaptchaResponse(**create_captcha(client_ip=ip))


@router.post("/parent/phone-check")
def parent_phone_check(req: PhoneCheckRequest, request: Request, db: Session = Depends(get_db)):
    """手机号注册状态查询 — 需图形验证码 + IP 限流，降低枚举风险（B10）。"""
    from app.services.auth_challenge_store import (
        challenge_get_count,
        challenge_incr,
    )

    ip, _ = _auth_ctx(request, None)
    ip_key = f"auth:phone_check:ip:{ip or 'unknown'}"
    if challenge_get_count(ip_key) >= 30:
        raise HTTPException(429, "查询过于频繁，请稍后再试")
    challenge_incr(ip_key, 3600)

    verify_captcha(req.captcha_id, req.captcha_code, consume=True)
    return {
        "ok": True,
        "message": "若号码有效，可继续获取验证码",
    }


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
def sms_login(
    req: SmsLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    ip, did = _auth_ctx(request, req.device_id)
    check_auth_allowed(db, client_ip=ip, phone=req.phone.strip(), device_id=did)
    try:
        verify_sms_code(req.phone, req.sms_code, SCENE_LOGIN)
        user = login_parent_by_sms(db, phone=req.phone.strip())
        clear_auth_failures(client_ip=ip, phone=req.phone.strip(), device_id=did)
        return _issue_and_respond(db, user, response)
    except HTTPException as e:
        if e.status_code in (400, 401, 404, 429):
            record_auth_failure(db, client_ip=ip, phone=req.phone.strip(), device_id=did)
        raise


@router.post("/sms/register", response_model=AuthResponse)
def sms_register(
    req: SmsRegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
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
        return _issue_and_respond(db, user, response)
    except HTTPException as e:
        if e.status_code in (400, 409, 429):
            record_auth_failure(db, client_ip=ip, phone=req.phone.strip(), device_id=did)
        raise


@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest, response: Response, db: Session = Depends(get_db)):
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
    return _issue_and_respond(db, user, response)


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip, did = _auth_ctx(request, None)

    if req.role == auth_service.ROLE_PARENT or (
        req.parent_phone and req.password and not req.login_name and not req.nickname
    ):
        if not req.parent_phone or not req.password:
            raise HTTPException(400, "请输入手机号和密码")
        from app.services.sms_service import normalize_phone

        try:
            phone = normalize_phone(req.parent_phone.strip())
        except HTTPException:
            raise HTTPException(400, "家长请使用11位手机号登录（不是昵称或孩子账号）")
        check_auth_allowed(db, client_ip=ip, phone=phone, device_id=did)
        user = auth_service.login_parent_by_password(db, phone, req.password)
        if not user:
            record_auth_failure(db, client_ip=ip, phone=phone, device_id=did)
            raise HTTPException(401, "手机号或密码错误")
        clear_auth_failures(client_ip=ip, phone=phone, device_id=did)
        return _issue_and_respond(db, user, response)

    if req.login_name and req.password:
        from app.core.password import verify_password

        login_name = req.login_name.strip()
        check_auth_allowed(db, client_ip=ip, device_id=did, login_name=login_name)
        user = auth_service.find_student_for_login(db, login_name)
        if not user or not verify_password(req.password, user.password_hash):
            record_auth_failure(db, client_ip=ip, device_id=did, login_name=login_name)
            raise HTTPException(401, "账号或密码错误")
        if not auth_service.has_active_parent_bind(db, user.id):
            raise HTTPException(403, "账号未绑定家长，请联系管理员")
        clear_auth_failures(client_ip=ip, device_id=did, login_name=login_name)
        return _issue_and_respond(db, user, response)

    raise HTTPException(400, "请提供有效的登录信息")


@router.post("/logout")
def logout(
    response: Response,
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    from app.core.session_cookie import clear_session_cookie
    from app.db.models import ChildUser
    from app.services.session_service import revoke_all_sessions

    user = db.get(ChildUser, user_id)
    role = (user.role if user else None) or auth_service.ROLE_STUDENT
    revoke_all_sessions(db, user_id)
    db.commit()
    clear_session_cookie(response, role=role)
    return {"ok": True}


@router.post("/change-password", response_model=AuthResponse)
def change_password(
    req: ChangePasswordRequest,
    response: Response,
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    user = auth_service.change_user_password(
        db,
        user_id,
        old_password=req.old_password,
        new_password=req.new_password,
    )
    return _attach_cookie_for_user(response, user)


@router.get("/wechat/config", response_model=WechatConfigResponse)
def wechat_config():
    ext = use_external_bind_mobile()
    return WechatConfigResponse(
        configured=wechat_configured(),
        app_id=wechat_app_id() or None,
        bind_mobile_url=build_external_bind_mobile_url() if ext else None,
        bind_mobile_return_url=bind_mobile_return_url() if ext else None,
        use_external_bind_mobile=ext,
    )


@router.get("/wechat/oauth-url", response_model=WechatOAuthUrlResponse)
def wechat_oauth_url(redirect: str = Query("", max_length=500)):
    if not wechat_configured():
        raise HTTPException(503, "微信公众号未配置")
    url = build_oauth_url(front_redirect=redirect)
    return WechatOAuthUrlResponse(url=url, configured=True)


@router.get("/wechat/exchange", response_model=AuthResponse)
def wechat_login_exchange(
    login_ticket: str = Query(..., min_length=8, max_length=128),
    response: Response = ...,
    db: Session = Depends(get_db),
):
    """OAuth 回调后一次性换取 session，避免 token 出现在 URL"""
    row = consume_login_exchange_ticket(login_ticket)
    user = auth_service.get_child_user(db, int(row["user_id"]))
    if not user:
        raise HTTPException(404, "用户不存在")
    return _attach_cookie_for_user(response, user)


@router.get("/wechat/callback")
def wechat_callback(
    code: str = Query(""),
    state: str = Query(""),
    db: Session = Depends(get_db),
):
    try:
        if not code:
            return RedirectResponse(
                url=frontend_wechat_error_url(
                    "微信未返回授权码：请从微信内打开链接，并确认公众平台已配置网页授权域名 jnaosoft.cn"
                ),
                status_code=302,
            )
        consume_oauth_state(state)
        openid, unionid = exchange_code_for_openid(code)
        user, bind_ticket, next_step = resolve_wechat_login(db, openid=openid, unionid=unionid)

        from app.services.parent_profile_service import parent_needs_company_verification

        # 已识别用户且已完成公司验证的，不再跳外链绑手机（避免死循环）
        if user is not None and next_step == "bind-phone":
            if parent_needs_company_verification(db, user):
                user = None
            else:
                bind_ticket = None
                snap = lookup_member_for_oauth(db, openid)
                next_step = finalize_wechat_login_user(
                    db, user, openid=openid, unionid=unionid, snap=snap
                )

        if next_step == "bind-phone" and use_external_bind_mobile() and user is None:
            ticket = bind_ticket
            if not ticket and user is None:
                snap = lookup_member_for_oauth(db, openid)
                ticket = create_bind_ticket(
                    openid=openid,
                    unionid=unionid,
                    wx_member_id=snap.wx_member_id if snap else None,
                )
            if ticket:
                return RedirectResponse(
                    url=build_external_bind_mobile_url(bind_ticket=ticket),
                    status_code=302,
                )
            return RedirectResponse(url=build_external_bind_mobile_url(), status_code=302)

        params = {"wx": "1", "next_step": next_step}
        if user:
            from app.services.session_service import issue_session

            issue_session(db, user)
            db.refresh(user)
            params["login_ticket"] = create_login_exchange_ticket(
                user_id=user.id,
                next_step=next_step,
                role=user.role or auth_service.ROLE_PARENT,
            )
        if bind_ticket:
            params["bind_ticket"] = bind_ticket

        return RedirectResponse(url=frontend_login_url(**params), status_code=302)
    except HTTPException as e:
        detail = e.detail if isinstance(e.detail, str) else "微信登录失败，请重新进入"
        return RedirectResponse(url=frontend_wechat_error_url(detail), status_code=302)
    except Exception:
        logger.exception("WeChat callback failed")
        return RedirectResponse(
            url=frontend_wechat_error_url("微信登录异常，请稍后重试或使用手机登录"),
            status_code=302,
        )


@router.post("/wechat/send-bind-sms", response_model=SmsSendResponse)
def wechat_send_bind_sms(req: WechatSendBindSmsRequest, request: Request, db: Session = Depends(get_db)):
    assert_bind_ticket_sms_allowed(req.bind_ticket, req.phone)
    ip, did = _auth_ctx(request, req.device_id)
    data = send_sms_code(
        db,
        phone=req.phone,
        scene=SCENE_BIND,
        client_ip=ip,
        device_id=did,
    )
    return SmsSendResponse(**data)


@router.post("/wechat/bind-phone", response_model=AuthResponse)
def wechat_bind_phone(
    req: WechatBindPhoneRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    ip, did = _auth_ctx(request, req.device_id)
    phone = req.phone.strip()
    check_auth_allowed(db, client_ip=ip, phone=phone, device_id=did)
    try:
        verify_sms_code(phone, req.sms_code, SCENE_BIND)
        user = complete_bind_phone(db, bind_ticket=req.bind_ticket, phone=phone)
        clear_auth_failures(client_ip=ip, phone=phone, device_id=did)
        return _issue_and_respond(db, user, response)
    except HTTPException as e:
        if e.status_code in (400, 429):
            record_auth_failure(db, client_ip=ip, phone=phone, device_id=did)
        raise


@router.post("/wechat/complete-external-bind", response_model=AuthResponse)
def wechat_complete_external_bind(
    req: WechatExternalBindRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """外链 m.jnao.com 绑手机完成后，凭 bind_ticket 换取登录 session。"""
    ip, did = _auth_ctx(request, req.device_id)
    check_auth_allowed(db, client_ip=ip, device_id=did)
    try:
        user = complete_external_bind_phone(db, bind_ticket=req.bind_ticket)
        clear_auth_failures(client_ip=ip, device_id=did)
        return _issue_and_respond(db, user, response)
    except HTTPException as e:
        if e.status_code in (400, 429):
            record_auth_failure(db, client_ip=ip, device_id=did)
        raise
