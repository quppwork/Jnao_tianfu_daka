"""管理员 API 模型"""

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    login_name: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)


class AdminParentOut(BaseModel):
    id: int
    parent_phone: str
    nickname: str
    child_quota: int
    children_count: int = 0
    created_at: str | None = None
    account_status: str | None = None
    display_phone: str | None = None


class AdminCreateParentRequest(BaseModel):
    parent_phone: str = Field(..., min_length=11, max_length=20)
    nickname: str = Field(..., min_length=1, max_length=50)
    password: str | None = Field(None, min_length=6, max_length=128)
    child_quota: int = Field(5, ge=0, le=999)


class AdminRestoreByPhoneRequest(BaseModel):
    phone: str | None = Field(None, min_length=11, max_length=20)
    nickname: str | None = Field(None, min_length=1, max_length=50)


class AdminParentListResponse(BaseModel):
    parents: list[AdminParentOut]


class AdminChildOut(BaseModel):
    id: int
    login_name: str | None
    nickname: str
    talent: str | None = None
    training_days: int = 0
    checkins: int = 0
    grade: str | None = None
    age: int | None = None
    parent_id: int | None = None
    parent_phone: str | None = None
    parent_nickname: str | None = None


class AdminChildListResponse(BaseModel):
    children: list[AdminChildOut]


class AdminUpdateParentRequest(BaseModel):
    nickname: str | None = Field(None, min_length=1, max_length=50)
    parent_phone: str | None = Field(None, min_length=11, max_length=20)
    password: str | None = Field(None, min_length=6, max_length=128)
    child_quota: int | None = Field(None, ge=0, le=999)


class AdminCreateChildRequest(BaseModel):
    parent_id: int = Field(..., ge=1)
    login_name: str = Field(..., min_length=2, max_length=50)
    nickname: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    grade: str | None = Field(None, max_length=20)
    age: int | None = Field(None, ge=3, le=25)


class AdminUpdateChildRequest(BaseModel):
    login_name: str | None = Field(None, min_length=2, max_length=50)
    nickname: str | None = Field(None, min_length=1, max_length=50)
    password: str | None = Field(None, min_length=6, max_length=128)
    grade: str | None = Field(None, max_length=20)
    age: int | None = Field(None, ge=3, le=25)


class AdminBindChildRequest(BaseModel):
    parent_id: int = Field(..., ge=1)


class LoginPolicyOut(BaseModel):
    admin_max_devices: int = 3
    parent_max_devices: int = 1
    student_max_devices: int = 1


class AdminPlatformConfigResponse(BaseModel):
    login_policy: LoginPolicyOut


class AdminUpdateLoginPolicyRequest(BaseModel):
    admin_max_devices: int | None = Field(None, ge=1, le=20)
    parent_max_devices: int | None = Field(None, ge=1, le=10)
    student_max_devices: int | None = Field(None, ge=1, le=10)


class AdminUpdatePlatformConfigRequest(BaseModel):
    login_policy: AdminUpdateLoginPolicyRequest


class AdminSessionOut(BaseModel):
    id: int
    device_label: str | None = None
    created_at: str | None = None
    last_active_at: str | None = None


class AdminParentDetailResponse(BaseModel):
    id: int
    parent_phone: str
    nickname: str
    child_quota: int
    children_count: int
    created_at: str | None = None
    children: list[AdminChildOut] = []
    active_sessions: list[AdminSessionOut] = []
    reconciled_count: int = 0
    pending_unbound_count: int = 0
    unbound_children: list[AdminChildOut] = []
    duplicate_parents: list[dict] = []
    canonical_parent_id: int | None = None
    is_duplicate_account: bool = False
    account_status: str | None = "active"
    removed_at: str | None = None


class AdminReconcileResponse(BaseModel):
    reconciled_count: int = 0
    children_count: int = 0
    children: list[AdminChildOut] = []


class AdminTrainingDayOut(BaseModel):
    date: str
    records: list[dict] = []


class AdminChildDetailResponse(BaseModel):
    id: int
    login_name: str | None
    nickname: str
    grade: str | None = None
    age: int | None = None
    talent: str | None = None
    talent_display: str | None = None
    training_days: int = 0
    checkins: int = 0
    overall_tier: int = 1
    parent_id: int | None = None
    parent_phone: str | None = None
    parent_nickname: str | None = None
    created_at: str | None = None
    training_progress: dict | None = None
    training_history_days: list[AdminTrainingDayOut] = []
    recent_plans: list[dict] = []
    active_sessions: list[AdminSessionOut] = []
    account_status: str | None = "active"
    removed_at: str | None = None


class BlacklistEntryOut(BaseModel):
    value: str
    reason: str | None = None
    created_at: str | None = None
    expires_at: str | None = None
    created_by: str | None = None


class AdminBlacklistResponse(BaseModel):
    ips: list[BlacklistEntryOut] = []
    phones: list[BlacklistEntryOut] = []
    devices: list[BlacklistEntryOut] = []
