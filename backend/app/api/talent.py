"""天赋测试 API — JNAO 报告代理 + 测评落库"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_student, get_authenticated_user, get_db
from app.core.biz_log import biz_event, biz_timer
from app.core.cache import (
    cache_get_json,
    cache_set_json,
    invalidate_user_assessment,
    invalidate_user_growth,
    invalidate_user_profile,
    invalidate_user_training,
    key_assessment_latest,
    ttl_env,
)
from app.db.models import ChildUser
from app.models.requests import ReportRequest
from app.schemas.training import AssessmentOut
from app.services import assessment_service
from app.services.jnao_client import jnao_get_report, jnao_submit
from app.services.report_talent_agent import (
    ReportTalentError,
    ask,
    ask_stream,
    list_messages,
)

router = APIRouter(prefix="/api/talent", tags=["talent"])

_ASSESSMENT_TTL = ttl_env("CACHE_TTL_ASSESSMENT", 600)


def _invalidate_assessment_caches(user_id: int) -> None:
    invalidate_user_assessment(user_id)
    invalidate_user_profile(user_id)
    invalidate_user_growth(user_id)
    invalidate_user_training(user_id)


@router.post("/jnao/submit")
async def jnao_submit_answer(
    answer: str = Query(..., description="35位01编码答案字符串"),
    uid: int = Query(..., description="用户ID"),
    type: int = Query(..., description="测试类型 0=成人 1=孩子"),
    child_user_id: int = Depends(get_authenticated_student),
):
    """代理提交答案到 JNAO，返回 record_id"""
    try:
        record_id = await jnao_submit(answer, uid, type)
        return {"code": 1, "data": {"id": record_id}}
    except Exception as e:
        raise HTTPException(502, f"JNAO 提交失败: {e}") from e


@router.get("/jnao/report/{record_id}")
async def jnao_report(
    record_id: str,
    child_user_id: int = Depends(get_authenticated_student),
):
    """代理获取 JNAO 报告 JSON"""
    try:
        report = await jnao_get_report(record_id)
        return {"code": 1, "data": report}
    except Exception as e:
        raise HTTPException(502, f"JNAO 报告获取失败: {e}") from e


@router.post("/report")
async def talent_report(
    req: ReportRequest,
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """提交答案 + 获取报告（一步完成），落库到当前登录用户（家长/学生均可）。"""
    with biz_timer("talent.report", test_type=req.type) as ctx:
        try:
            record_id = await jnao_submit(req.answer, req.uid, req.type)
            report = await jnao_get_report(record_id)
            assessment_id = None
            conflict = False
            locked = False
            lock_msg = None
            current_talent = None
            user = db.get(ChildUser, user_id)
            if user and user.profile_json:
                current_talent = (user.profile_json or {}).get("talent_primary")
            row = assessment_service.save_assessment(
                db,
                child_user_id=user_id,
                jnao_record_id=str(record_id),
                answer_bitstring=req.answer,
                test_type=req.type,
                report=report,
            )
            assessment_id = row.id
            conflict = getattr(row, "_talent_conflict", False)
            locked = getattr(row, "_talent_locked", False)
            last_chance = getattr(row, "_talent_last_chance", False)
            _invalidate_assessment_caches(user_id)
            if locked:
                lock_msg = assessment_service.TALENT_LOCK_MSG
            if conflict and user:
                db.refresh(user)
                current_talent = (user.profile_json or {}).get("talent_primary") or current_talent
            ctx["fields"]["assessment_id"] = assessment_id
            ctx["fields"]["conflict"] = conflict
            ctx["fields"]["locked"] = locked
            return {
                "code": 1,
                "data": report,
                "assessment_id": assessment_id,
                "talent_conflict": conflict,
                "talent_locked": locked,
                "talent_last_chance": last_chance,
                "lock_message": lock_msg,
                "current_talent": current_talent,
            }
        except Exception as e:
            ctx["result"] = "error"
            ctx["level"] = "error"
            ctx["fields"]["err"] = type(e).__name__
            raise HTTPException(502, str(e)) from e


@router.post("/assessment")
async def save_assessment_endpoint(
    req: ReportRequest,
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """测评完成并落库（家长/学生均可）。"""
    try:
        record_id = await jnao_submit(req.answer, req.uid, req.type)
        report = await jnao_get_report(record_id)
        row = assessment_service.save_assessment(
            db,
            child_user_id=user_id,
            jnao_record_id=str(record_id),
            answer_bitstring=req.answer,
            test_type=req.type,
            report=report,
        )
        user = db.get(ChildUser, user_id)
        pj = (user.profile_json or {}) if user else {}
        current = pj.get("talent_primary", "")
        _invalidate_assessment_caches(user_id)
        return {
            "code": 1,
            "data": report,
            "assessment_id": row.id,
            "talent_code": row.talent_code,
            "talent_tag": row.talent_tag,
            "talent_conflict": getattr(row, "_talent_conflict", False),
            "talent_locked": getattr(row, "_talent_locked", False),
            "current_talent": current,
            "lock_message": assessment_service.TALENT_LOCK_MSG if getattr(row, "_talent_locked", False) else None,
        }
    except Exception as e:
        raise HTTPException(502, str(e)) from e


@router.get("/assessment/history")
def assessment_history(
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
    limit: int = 30,
):
    """家长/学生均可：按报告所有者拉取历史。"""
    return {"items": assessment_service.list_assessments(db, user_id, limit)}


@router.get("/assessment/latest", response_model=AssessmentOut)
def latest_assessment(
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """最新测评；无 JNAO 记录时若有引导页自选天赋也返回 200。家长/学生均可。"""
    key = key_assessment_latest(user_id)
    cached = cache_get_json(key)
    if cached is not None:
        return AssessmentOut(**cached)

    assessment_service.repair_onboarding_talent(db, user_id)
    row = assessment_service.get_latest_assessment(db, user_id)
    if row:
        out = AssessmentOut(
            id=row.id,
            child_user_id=row.child_user_id,
            talent_primary=row.talent_primary,
            talent_tag=row.talent_tag,
            talent_code=row.talent_code,
            assessed_at=row.assessed_at.isoformat() if row.assessed_at else None,
            jnao_record_id=row.jnao_record_id,
            talent_source="assessment",
        )
        cache_set_json(key, out.model_dump(), _ASSESSMENT_TTL)
        return out
    eff = assessment_service.resolve_effective_talent(db, user_id)
    if eff and eff.get("talent_code"):
        user = db.get(ChildUser, user_id)
        onboarding = {}
        if user and isinstance(user.profile_json, dict):
            onboarding = user.profile_json.get("onboarding") or {}
        out = AssessmentOut(
            id=0,
            child_user_id=user_id,
            talent_primary=eff.get("talent_primary"),
            talent_tag=eff.get("talent_tag"),
            talent_code=eff.get("talent_code"),
            assessed_at=onboarding.get("completed_at"),
            jnao_record_id=None,
            talent_source=eff.get("talent_source"),
        )
        cache_set_json(key, out.model_dump(), _ASSESSMENT_TTL)
        return out
    raise HTTPException(404, "尚未完成天赋测评")


@router.get("/assessment/{assessment_id}")
def get_assessment(
    assessment_id: int,
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """按报告 ID 读测评正文。归属当前登录用户即可（家长/学生）。"""
    row = assessment_service.get_assessment_by_id(db, assessment_id, user_id)
    if not row:
        raise HTTPException(404, "测评记录不存在")
    report = row.report_json or {}
    return {
        "code": 1,
        "data": report,
        "assessment_id": row.id,
        "talent_primary": row.talent_primary,
        "test_type": row.test_type,  # 0 adult, 1 child
        "assessed_at": (
            row.assessed_at.isoformat() if row.assessed_at else None
        ),
    }


class ReportTalentChatIn(BaseModel):
    content: str = Field(..., max_length=2000)


@router.get("/assessment/{assessment_id}/chat")
def report_talent_chat_history(
    assessment_id: int,
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """按报告 ID 读取天赋解答对话。开场白不入库。家长/学生均可，归属看报告所有者。"""
    row = assessment_service.get_assessment_by_id(db, assessment_id, user_id)
    if not row:
        raise HTTPException(404, "测评记录不存在")
    try:
        return list_messages(db, row)
    except ReportTalentError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.post("/assessment/{assessment_id}/chat")
async def report_talent_chat_send(
    assessment_id: int,
    req: ReportTalentChatIn,
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """提交本轮问题。ReAct + talent_doc_retrieve，记忆只写入这份报告。"""
    row = assessment_service.get_assessment_by_id(db, assessment_id, user_id)
    if not row:
        raise HTTPException(404, "测评记录不存在")
    try:
        return await ask(db, row, req.content)
    except ReportTalentError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.post("/assessment/{assessment_id}/chat/stream")
async def report_talent_chat_stream(
    assessment_id: int,
    req: ReportTalentChatIn,
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """SSE 流式天赋解答：token 增量 → done 带权威消息与 citations。

    前端契约：`type` ∈ token | replace | error | done | [DONE]。
    """
    from app.core.sse import SSE_HEADERS, emit_event_stream, sse_done, sse_json

    row = assessment_service.get_assessment_by_id(db, assessment_id, user_id)
    if not row:
        raise HTTPException(404, "测评记录不存在")

    async def events():
        try:
            async for chunk in emit_event_stream(ask_stream(db, row, req.content)):
                yield chunk
        except ReportTalentError as e:
            yield sse_json({"type": "error", "message": e.message})
            yield sse_done()
        except Exception:
            yield sse_json({"type": "error", "message": "天赋解答暂时异常，请稍后再试"})
            yield sse_done()

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.delete("/assessment/{assessment_id}")
def delete_assessment_endpoint(
    assessment_id: int,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """删除历史测评（归档后从主表移除，定时全库备份保留副本）"""
    try:
        result = assessment_service.delete_assessment(db, assessment_id, child_user_id)
        _invalidate_assessment_caches(child_user_id)
        return result
    except assessment_service.AssessmentError as e:
        raise HTTPException(e.status_code, e.message) from e
