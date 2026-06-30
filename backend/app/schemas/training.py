"""Pydantic 请求/响应模型"""

from datetime import date, time

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    parent_phone: str = Field(..., min_length=11, max_length=20)
    nickname: str = Field(..., min_length=1, max_length=50)
    jnao_uid: str | None = None


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
    watch_progress: dict | None = None
    video_complete: bool = False
    media_hidden: bool = False


class WatchProgressRequest(BaseModel):
    watched_sec: float = Field(..., ge=0)
    duration_sec: float | None = Field(None, ge=0)


class WatchProgressResponse(BaseModel):
    item_id: int
    watch_progress: dict
    video_complete: bool


class OptionalOfferOut(BaseModel):
    skill: str
    weight: float = 0
    suggested: bool = False
    content_type: str = "audio"
    requires_confirm: bool = True
    status: str = "pending"  # pending | accepted | declined


class OptionalChoiceRequest(BaseModel):
    skill: str = Field(..., min_length=1, max_length=50)
    accept: bool = Field(..., description="true=加入今日训练，false=今天不练")


class TrainingTodayResponse(BaseModel):
    plan_id: int
    plan_date: date
    status: str
    report_text: str | None
    content_index: int
    main_line: str | None = None
    main_line_name: str | None = None
    progress_main_line: str | None = None
    progress_main_line_name: str | None = None
    planned_minutes: int | None = None
    media_exhausted: bool = False
    items: list[TrainingItemOut]
    day_locked: bool = False
    globally_cutoff: bool = False
    training_day: str | None = None
    server_now: str | None = None
    unlock_at: str | None = None
    seconds_until_unlock: int | None = None
    cutoff_at: str | None = None
    new_day_at: str | None = None
    seconds_until_cutoff: int | None = None
    seconds_until_new_day: int | None = None
    day_transition: bool = False
    new_day_ready: bool = True
    lesson_day: int | None = None
    training_day_number: int | None = None
    schedule_mode: str | None = None
    optional_offers: list[OptionalOfferOut] = Field(default_factory=list)
    timer_phase: str | None = None
    timer_end_at: str | None = None
    timer_planned_seconds: int | None = None
    timer_remaining_seconds: int | None = None


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


class CheckinAdvanceDetail(BaseModel):
    rule_key: str | None = None
    skill: str | None = None
    rule_type: str | None = None
    met: bool = False
    minutes: float | None = None
    words: float | None = None
    words_per_minute: float | None = None
    required_wpm: float | None = None
    grade_band: str | None = None
    required_words: int | None = None
    accuracy_pct: float | None = None
    required_pct: float | None = None
    message: str | None = None


class CheckinTrainingProgress(BaseModel):
    main_line: str | None = None
    main_line_from: str | None = None
    main_line_to: str | None = None
    main_line_advanced: bool = False
    advance_pending: bool = False
    pending_main_line_to: str | None = None
    advance_met: bool = False
    advance_rule_key: str | None = None
    advance_detail: CheckinAdvanceDetail | None = None
    advance_message: str | None = None
    skills_bumped: list[str] = Field(default_factory=list)
    content_index: int | None = None


class CheckinResponse(BaseModel):
    record_id: int
    plan_status: str
    training_progress: CheckinTrainingProgress | None = None


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
    train_date: str | None = None
    checkin_at: str | None = None
    checkin_time: str | None = None
    ability_type: str | None
    time_spent: str | None = None
    content: str | None
    result: str | None = None
    note: str | None = None
    attitude_pct: int | None
    phase_blocks: list[str] = Field(default_factory=list)
    cards: list[dict] = Field(default_factory=list)
    created_at: str | None = None


class CheckinHistoryDayOut(BaseModel):
    date: str
    records: list[CheckinRecordOut]


class CheckinHistoryResponse(BaseModel):
    items: list[CheckinRecordOut]
    days: list[CheckinHistoryDayOut] = Field(default_factory=list)


class CheckinDeleteResponse(BaseModel):
    deleted: bool
    plan_status: str | None = None


class TrainingProgressResponse(BaseModel):
    total_checkins: int
    content_index: int
    talent_code: int | None
    talent_tag: str | None
    talent_primary: str | None = None
    assessment_id: int | None = None
    has_assessment: bool = False
    needs_assessment: bool = False
    today_completed: bool


class TrainingEntryResponse(BaseModel):
    has_assessment: bool
    needs_assessment: bool
    message: str | None = None
    assessment_id: int | None = None
    talent_primary: str | None = None
    talent_tag: str | None = None
    talent_code: int | None = None
    talent_source: str | None = None
    talent_conflict: bool = False
    pending_talent: dict | None = None
    onboarding_completed: bool = False
    total_checkins: int = 0
    content_index: int = 0
    today_completed: bool = False
    day_locked: bool = False
    training_day: str | None = None
    server_now: str | None = None
    unlock_at: str | None = None
    seconds_until_unlock: int | None = None
    cutoff_at: str | None = None
    new_day_at: str | None = None
    seconds_until_cutoff: int | None = None
    seconds_until_new_day: int | None = None
    day_transition: bool = False
    new_day_ready: bool = True


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
    id: int = 0
    child_user_id: int
    talent_primary: str | None
    talent_tag: str | None
    talent_code: int | None
    assessed_at: str | None
    jnao_record_id: str | None = None
    talent_source: str | None = None
