"""今日训练 API — 方案、打卡、时段"""

from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import (
    get_authenticated_student,
    get_authenticated_user,
    get_db,
)
from app.core.cache import (
    cache_get_json,
    cache_set_json,
    key_train_progress,
    ttl_env,
)
from app.schemas.training import (
    CheckinDeleteResponse,
    CheckinHistoryResponse,
    CheckinRecordOut,
    CheckinRequest,
    CheckinResponse,
    CheckinUpdateRequest,
    PlanCustomizeRequest,
    ScheduleRequest,
    TalentVideoResponse,
    TrainingEntryResponse,
    TrainingProgressResponse,
    TrainingTodayResponse,
    WatchProgressRequest,
    WatchProgressResponse,
    WindowResponse,
    WindowSetRequest,
    WindowStatusResponse,
)
from app.services import training_service
from app.services.training_elective_service import (
    get_elective_offers,
    submit_elective_checkin,
)
from app.services.training_plan_generator import ensure_plan_report
from app.services.training_schedule_service import (
    schedule_training_by_duration,
)
from app.services.training_service import TrainingError
from app.services.video_push_service import get_talent_training_video, get_talent_video_raw_url

router = APIRouter(prefix="/api/training", tags=["training"])


def _resolve_training_stream_user(
    request: Request,
    *,
    item_id: int,
    media: str,
    user_id: int | None,
    mt: str | None,
    x_session_token: str | None,
    session_token: str | None,
    db: Session,
) -> int:
    """Cookie/Header 会话 或 短期 mt 签名（供 video/audio 标签 src 使用）。"""
    from app.core.media_stream_token import verify_media_stream_token
    from app.db.models import ChildUser
    from app.services import auth_service

    def _ensure_student(uid: int) -> int:
        user = db.get(ChildUser, uid)
        if not user or (user.role or auth_service.ROLE_STUDENT) != auth_service.ROLE_STUDENT:
            raise HTTPException(403, "需要学生账号")
        if not auth_service.has_active_parent_bind(db, uid):
            raise HTTPException(403, "账号未绑定家长，请联系管理员")
        return uid

    if user_id and mt and verify_media_stream_token(mt, item_id, user_id, media):
        user = db.get(ChildUser, user_id)
        if not user or (user.role or auth_service.ROLE_STUDENT) != auth_service.ROLE_STUDENT:
            raise HTTPException(403, "需要学生账号")
        return user_id

    from main import app

    override = app.dependency_overrides.get(get_authenticated_student)
    if override is not None:
        return override(user_id=user_id)

    uid = get_authenticated_user(
        request, user_id, None, x_session_token, session_token, db
    )
    return _ensure_student(uid)


@router.post("/schedule", response_model=TrainingTodayResponse)
async def schedule_training(
    req: ScheduleRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
    plan_date: date | None = Query(None),
):
    """按今日训练时长排课：豆包路由 A/B 音频 + 天赋固定视频"""
    try:
        return await schedule_training_by_duration(
            db, child_user_id, req.planned_minutes, plan_date=plan_date
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/video/talent", response_model=TalentVideoResponse)
def talent_training_video(
    auth_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """天赋能力视频讲解 — 返回 OSS 五者天赋视频（家长/学生均可观看）"""
    return get_talent_training_video(None, db=db)


@router.get("/video/talent/stream")
def talent_video_stream(
    request: Request,
    auth_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """代理 OSS 视频流 — 后端读取 OSS，转发给前端（绕过 CORS / 签名过期）"""
    from app.services.oss_stream_service import stream_oss_media

    url = get_talent_video_raw_url(db)
    if not url:
        raise HTTPException(404, "视频资源未找到")
    if url.startswith("/static/"):
        from pathlib import Path
        from fastapi.responses import FileResponse

        static_path = Path(__file__).resolve().parents[2] / url.lstrip("/")
        if static_path.is_file():
            return FileResponse(static_path, media_type="video/mp4", headers={"Accept-Ranges": "bytes"})
        raise HTTPException(404, "视频资源未找到")
    return stream_oss_media(url, range_header=request.headers.get("range"))


@router.get("/items/{item_id}/stream")
def training_item_media_stream(
    item_id: int,
    request: Request,
    media: str = Query("video", pattern="^(audio|video)$"),
    user_id: int | None = Query(None, ge=1),
    mt: str | None = Query(None, description="短期流签名（API 返回的 video_url/audio_url 自带）"),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
    session_token: str | None = Query(None, description="会话令牌（已弃用，请用 Cookie）"),
    db: Session = Depends(get_db),
):
    """训练项音视频流 — 鉴权后从 OSS 代理播放（避免签名 URL 过期）"""
    from app.db.models import TrainingItem, TrainingPlan
    from app.services.oss_stream_service import stream_oss_media

    child_user_id = _resolve_training_stream_user(
        request,
        item_id=item_id,
        media=media,
        user_id=user_id,
        mt=mt,
        x_session_token=x_session_token,
        session_token=session_token,
        db=db,
    )

    item = db.get(TrainingItem, item_id)
    if not item:
        raise HTTPException(404, "训练项不存在")
    plan = db.get(TrainingPlan, item.plan_id)
    if not plan or plan.child_user_id != child_user_id:
        raise HTTPException(403, "无权访问该训练项")

    stored = item.video_url if media == "video" else item.audio_url
    if not stored:
        raise HTTPException(404, f"该训练项无{media}资源")
    return stream_oss_media(stored, range_header=request.headers.get("range"))


@router.post(
    "/items/{item_id}/watch-progress",
    response_model=WatchProgressResponse,
)
def report_watch_progress(
    item_id: int,
    req: WatchProgressRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    try:
        return training_service.record_watch_progress(
            db,
            child_user_id,
            item_id,
            watched_sec=req.watched_sec,
            duration_sec=req.duration_sec,
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/entry", response_model=TrainingEntryResponse)
def training_entry(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """训练页入口：优先检查最新天赋并同步今日方案状态"""
    try:
        return training_service.get_training_entry(db, child_user_id)
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/today", response_model=TrainingTodayResponse)
async def training_today(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
    plan_date: date | None = Query(None),
    skip_ai: bool = Query(False, description="跳过 AI 生成，加快首屏"),
):
    """今日训练方案：按天赋推送音频 + AI 生成今日指令（参考昨日打卡）"""
    try:
        return await ensure_plan_report(
            db, child_user_id, plan_date, skip_ai=skip_ai
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.post("/checkin", response_model=CheckinResponse)
def training_checkin(
    req: CheckinRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    try:
        return training_service.submit_checkin(
            db,
            child_user_id,
            plan_id=req.plan_id,
            item_id=req.item_id,
            ability_type=req.ability_type,
            time_spent=req.time_spent,
            content=req.content,
            result=req.result,
            note=req.note,
            attitude_pct=req.attitude_pct,
            cards=req.cards,
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/checkin/today", response_model=list[CheckinRecordOut])
def checkin_today(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
    plan_date: date | None = Query(None),
):
    return training_service.get_today_checkins(db, child_user_id, plan_date)


@router.get("/checkin/{record_id}", response_model=CheckinRecordOut)
def get_checkin(
    record_id: int,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    try:
        return training_service.get_checkin_record(
            db, child_user_id, record_id
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.put("/checkin/{record_id}")
def update_checkin(
    record_id: int,
    req: CheckinUpdateRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    try:
        return training_service.update_checkin_record(
            db,
            child_user_id,
            record_id,
            ability_type=req.ability_type,
            time_spent=req.time_spent,
            content=req.content,
            result=req.result,
            note=req.note,
            attitude_pct=req.attitude_pct,
            cards=req.cards,
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.delete("/checkin/{record_id}", response_model=CheckinDeleteResponse)
def delete_checkin(
    record_id: int,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    try:
        return training_service.delete_checkin_record(
            db, child_user_id, record_id
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


# ── v2.0 选修弹窗 ──

@router.get("/elective/list")
def elective_list(
    planned_minutes: int = Query(0, description="今日训练时长（分钟）"),
    overall_tier: int = Query(1, description="整体 Tier"),
):
    """获取可用的选修技能列表"""
    return {"offers": get_elective_offers(planned_minutes, overall_tier)}


@router.post("/elective")
def elective_checkin(
    req: dict,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """提交选修打卡（多元感知等）"""
    from app.services.training_service import TrainingError

    try:
        return submit_elective_checkin(
            db,
            child_user_id,
            plan_id=req.get("plan_id", 0),
            skill=req.get("skill", ""),
            cards=req.get("cards"),
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.post("/plan/elective-toggle", response_model=TrainingTodayResponse)
def plan_elective_toggle(
    req: dict,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """开关选修项：action="add" 追加，action="remove" 移除"""
    try:
        return training_service.toggle_elective_item(
            db, child_user_id,
            plan_id=req.get("plan_id", 0),
            skill=req.get("skill", ""),
            action=req.get("action", ""),
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/progress", response_model=TrainingProgressResponse)
def training_progress(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    key = key_train_progress(child_user_id)
    cached = cache_get_json(key)
    if cached is not None:
        return cached
    data = training_service.get_progress(db, child_user_id)
    cache_set_json(key, data, ttl_env("CACHE_TTL_TRAINING_PROGRESS", 60))
    return data


@router.post("/window", response_model=WindowResponse)
def set_window(
    req: WindowSetRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    try:
        return training_service.set_training_window(
            db, child_user_id, req.start_time, req.end_time
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/window", response_model=WindowResponse)
def get_window(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    row = training_service.get_training_window(db, child_user_id)
    if not row:
        raise HTTPException(404, "今日尚未设置训练时段")
    return row


@router.delete("/window")
def delete_window(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    deleted = training_service.clear_training_window(db, child_user_id)
    return {"deleted": deleted}


@router.get("/window/status", response_model=WindowStatusResponse)
def window_status(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    return training_service.get_window_status(db, child_user_id)


@router.post("/plan/customize", response_model=TrainingTodayResponse)
def customize_plan(
    req: PlanCustomizeRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """整体替换今日训练方案的项目（不改技能等级进度）"""
    try:
        return training_service.customize_plan_items(
            db, child_user_id, req.plan_id, req.skills
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.post("/plan/media-exhausted", response_model=TrainingTodayResponse)
def mark_plan_media_exhausted(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
    plan_date: date | None = Query(None),
):
    """设定时长用尽：隐藏音视频，打卡仍开放至训练日截止"""
    try:
        return training_service.mark_today_media_exhausted(
            db, child_user_id, plan_date
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/report/today", response_model=TrainingTodayResponse)
async def training_report_today(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
    force: bool = Query(False, description="强制重新生成 AI 方案"),
    skip_ai: bool = Query(False),
):
    try:
        return await ensure_plan_report(
            db, child_user_id, force=force, skip_ai=skip_ai
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/report/{plan_date}", response_model=TrainingTodayResponse)
def training_report_by_date(
    plan_date: date,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    data = training_service.get_plan_by_date(db, child_user_id, plan_date)
    if not data:
        raise HTTPException(404, "该日期无训练方案")
    return data


@router.get("/history", response_model=CheckinHistoryResponse)
def training_history(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
    limit: int = Query(60, ge=1, le=200),
    group_by_day: bool = Query(True),
    exclude_today: bool = Query(False),
):
    items = training_service.get_checkin_history(
        db, child_user_id, limit, exclude_today=exclude_today
    )
    if group_by_day:
        days = training_service.group_checkin_history_by_day(items)
    else:
        days = []
    return {"items": items, "days": days}
