"""Pydantic 请求/响应模型"""

from datetime import date, time

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    parent_phone: str = Field(..., min_length=11, max_length=20)
    nickname: str = Field(..., min_length=1, max_length=50)
    jnao_uid: str | None = None


class LoginRequest(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=50)
    parent_phone: str | None = None


class RegisterResponse(BaseModel):
    child_user_id: int
    parent_phone: str
    nickname: str


class TrainingItemOut(BaseModel):
    id: int
    sort_order: int
    title: str | None
    audio_url: str | None
    video_url: str | None
    duration_min: int | None
    instructions: str | None
    checkin_status: str
    block: str | None = None
    item_type: str | None = None


class TrainingTodayResponse(BaseModel):
    plan_id: int
    plan_date: date
    status: str
    report_text: str | None
    content_index: int
    planned_minutes: int | None = None
    items: list[TrainingItemOut]


class ScheduleRequest(BaseModel):
    planned_minutes: int = Field(..., ge=5, le=480, description="今日计划训练总时长（分钟）")


class TalentVideoResponse(BaseModel):
    title: str
    url: str
    talent_code: int | None = None
    source: str | None = None


class CheckinRequest(BaseModel):
    plan_id: int = Field(..., ge=1)
    item_id: int | None = Field(None, ge=1)
    ability_type: str | None = Field(None, max_length=50)
    time_spent: str | None = Field(None, max_length=20)
    content: str | None = Field(None, max_length=2000)
    result: str | None = Field(None, max_length=500)
    note: str | None = Field(None, max_length=500)
    attitude_pct: int | None = Field(None, ge=0, le=100)
    cards: list[dict] | None = Field(None, max_length=20)


class CheckinResponse(BaseModel):
    record_id: int
    plan_status: str


class CheckinUpdateRequest(BaseModel):
    ability_type: str | None = Field(None, max_length=50)
    time_spent: str | None = Field(None, max_length=20)
    content: str | None = Field(None, max_length=2000)
    result: str | None = Field(None, max_length=500)
    note: str | None = Field(None, max_length=500)
    attitude_pct: int | None = Field(None, ge=0, le=100)
    cards: list[dict] | None = Field(None, max_length=20)


class CheckinRecordOut(BaseModel):
    id: int
    plan_id: int | None
    item_id: int | None
    ability_type: str | None
    time_spent: str | None = None
    content: str | None
    result: str | None = None
    note: str | None = None
    attitude_pct: int | None
    cards: list[dict] = Field(default_factory=list)
    created_at: str | None = None


class CheckinDeleteResponse(BaseModel):
    deleted: bool
    plan_status: str | None = None


class TrainingProgressResponse(BaseModel):
    total_checkins: int
    content_index: int
    talent_code: int | None
    talent_tag: str | None
    today_completed: bool


class WindowSetRequest(BaseModel):
    start_time: str = Field(..., description="HH:MM")
    end_time: str = Field(..., description="HH:MM")


class WindowResponse(BaseModel):
    train_date: date
    start_time: str
    end_time: str


class WindowStatusResponse(BaseModel):
    in_window: bool
    train_date: date
    start_time: str | None
    end_time: str | None


class AssessmentOut(BaseModel):
    id: int
    child_user_id: int
    talent_primary: str | None
    talent_tag: str | None
    talent_code: int | None
    assessed_at: str | None
    jnao_record_id: str | None
