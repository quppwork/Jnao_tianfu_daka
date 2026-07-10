"""认证与家长相关 Pydantic 模型"""

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    parent_phone: str = Field(..., min_length=11, max_length=20)
    nickname: str = Field(..., min_length=1, max_length=50)
    password: str | None = Field(None, min_length=6, max_length=128)
    role: str = Field("student", pattern="^(student|parent)$")
    login_name: str | None = Field(None, min_length=2, max_length=50)
    jnao_uid: str | None = None


class LoginRequest(BaseModel):
    parent_phone: str | None = Field(None, min_length=11, max_length=20)
    nickname: str | None = Field(None, min_length=1, max_length=50)
    login_name: str | None = Field(None, min_length=2, max_length=50)
    password: str | None = Field(None, min_length=6, max_length=128)
    role: str | None = Field(None, pattern="^(student|parent)$")


class AuthResponse(BaseModel):
    child_user_id: int
    parent_phone: str
    nickname: str
    role: str = "student"
    login_name: str | None = None
    session_token: str | None = None
    profile_complete: bool = True
    missing_fields: list[str] = Field(default_factory=list)
    login_channel: str = "standard"
    account_ready: bool = True
    next_step: str = "home"
    bind_ticket: str | None = None
    must_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class WechatOAuthUrlResponse(BaseModel):
    url: str
    configured: bool = True


class WechatConfigResponse(BaseModel):
    configured: bool
    app_id: str | None = None
    bind_mobile_url: str | None = None
    bind_mobile_return_url: str | None = None
    use_external_bind_mobile: bool = False


class WechatBindPhoneRequest(BaseModel):
    bind_ticket: str = Field(..., min_length=8, max_length=128)
    phone: str = Field(..., min_length=11, max_length=20)
    sms_code: str = Field(..., min_length=4, max_length=8)
    device_id: str | None = Field(None, max_length=64)


class WechatExternalBindRequest(BaseModel):
    bind_ticket: str = Field(..., min_length=8, max_length=128)
    device_id: str | None = Field(None, max_length=64)


class WechatSendBindSmsRequest(BaseModel):
    bind_ticket: str = Field(..., min_length=8, max_length=128)
    phone: str = Field(..., min_length=11, max_length=20)
    device_id: str | None = Field(None, max_length=64)


class CaptchaResponse(BaseModel):
    captcha_id: str
    image_base64: str
    image_format: str = "png"
    expires_in: int = 120


class SmsSendRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20)
    scene: str = Field("login", pattern="^(login|register|bind)$")
    captcha_id: str | None = Field(None, max_length=64)
    captcha_code: str | None = Field(None, max_length=8)
    device_id: str | None = Field(None, max_length=64)


class SmsSendResponse(BaseModel):
    ok: bool = True
    message: str = "若号码有效，验证码已发送"
    expires_in: int = 300
    resend_after: int = 60
    debug_code: str | None = None


class SmsLoginRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20)
    sms_code: str = Field(..., min_length=4, max_length=8)
    device_id: str | None = Field(None, max_length=64)


class SmsRegisterRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20)
    sms_code: str = Field(..., min_length=4, max_length=8)
    real_name: str = Field(..., min_length=2, max_length=20)
    nickname: str = Field(..., min_length=2, max_length=20)
    password: str | None = Field(None, min_length=8, max_length=128)
    device_id: str | None = Field(None, max_length=64)


class ParentProfileResponse(BaseModel):
    id: int
    parent_phone: str
    nickname: str
    real_name: str | None = None
    has_password: bool = False
    phone_verified: bool = False
    profile_complete: bool = True
    missing_fields: list[str] = Field(default_factory=list)
    login_channel: str = "standard"
    account_ready: bool = True
    next_step: str = "home"
    session_token: str | None = None


class ParentProfileUpdateRequest(BaseModel):
    nickname: str | None = Field(None, min_length=1, max_length=50)
    real_name: str | None = Field(None, min_length=1, max_length=50)
    password: str | None = Field(None, min_length=6, max_length=128)
    old_password: str | None = Field(None, min_length=6, max_length=128)
    require_password: bool = False


class PhoneCheckRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20)
    captcha_id: str = Field(..., min_length=1, max_length=64)
    captcha_code: str = Field(..., min_length=4, max_length=8)


# 兼容旧引用
RegisterResponse = AuthResponse


class CreateChildRequest(BaseModel):
    login_name: str = Field(..., min_length=2, max_length=30)
    nickname: str = Field(..., min_length=2, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)
    grade: str | None = Field(None, max_length=20)       # 🆕 年级
    age: int | None = Field(None, ge=3, le=120)            # 🆕 年龄（与前端 picker 一致）
    # --- 以下字段已建表，前端暂不使用，请勿删除 ---
    region: str | None = Field(None, max_length=50)       # 🆕 地区（前端暂不采集）


class UpdateChildRequest(BaseModel):
    nickname: str | None = Field(None, min_length=2, max_length=20)
    password: str | None = Field(None, min_length=8, max_length=128)
    grade: str | None = Field(None, max_length=20)        # 🆕
    age: int | None = Field(None, ge=3, le=120)            # 🆕 年龄（与前端 picker 一致）
    region: str | None = Field(None, max_length=50)       # 🆕


class ChildSummaryOut(BaseModel):
    id: int
    login_name: str | None
    nickname: str
    talent: str | None = None
    training_days: int = 0
    checkins: int = 0
    grade: str | None = None
    age: int | None = None                                 # 🆕
    region: str | None = None                               # 🆕


class ParentChildrenResponse(BaseModel):
    children: list[ChildSummaryOut]


class ParentQuotaResponse(BaseModel):
    limit: int
    used: int
    remaining: int
    can_add: bool


class ChildDetailResponse(BaseModel):
    """预留：家长查看孩子详情摘要"""
    id: int
    login_name: str | None
    nickname: str
    talent: str | None = None
    training_days: int = 0
    checkins: int = 0
    grade: str | None = None
    school_stage: str | None = None
  # 后续可扩展：最近训练、测评摘要等
