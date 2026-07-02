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


# 兼容旧引用
RegisterResponse = AuthResponse


class CreateChildRequest(BaseModel):
    login_name: str = Field(..., min_length=2, max_length=50)
    nickname: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    grade: str | None = Field(None, max_length=20)       # 🆕 年级
    age: int | None = Field(None, ge=3, le=25)            # 🆕 年龄
    # --- 以下字段已建表，前端暂不使用，请勿删除 ---
    region: str | None = Field(None, max_length=50)       # 🆕 地区（前端暂不采集）


class UpdateChildRequest(BaseModel):
    nickname: str | None = Field(None, min_length=1, max_length=50)
    password: str | None = Field(None, min_length=6, max_length=128)
    grade: str | None = Field(None, max_length=20)        # 🆕
    age: int | None = Field(None, ge=3, le=25)            # 🆕
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
