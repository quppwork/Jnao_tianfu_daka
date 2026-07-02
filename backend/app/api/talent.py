"""天赋测试 API — JNAO 报告代理 + 测评落库"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_user, get_db
from app.db.models import ChildUser
from app.models.requests import ReportRequest
from app.schemas.training import AssessmentOut
from app.services import assessment_service
from app.services.jnao_client import jnao_get_report, jnao_submit

router = APIRouter(prefix="/api/talent", tags=["talent"])


@router.post("/jnao/submit")
async def jnao_submit_answer(
    answer: str = Query(..., description="35位01编码答案字符串"),
    uid: int = Query(..., description="用户ID"),
    type: int = Query(..., description="测试类型 0=成人 1=孩子"),
):
    """代理提交答案到 JNAO，返回 record_id"""
    try:
        record_id = await jnao_submit(answer, uid, type)
        return {"code": 1, "data": {"id": record_id}}
    except Exception as e:
        raise HTTPException(502, f"JNAO 提交失败: {e}") from e


@router.get("/jnao/report/{record_id}")
async def jnao_report(record_id: str):
    """代理获取 JNAO 报告 JSON"""
    try:
        report = await jnao_get_report(record_id)
        return {"code": 1, "data": report}
    except Exception as e:
        raise HTTPException(502, f"JNAO 报告获取失败: {e}") from e


@router.post("/report")
async def talent_report(req: ReportRequest, db: Session = Depends(get_db)):
    """提交答案 + 获取报告（一步完成），可选落库"""
    try:
        record_id = await jnao_submit(req.answer, req.uid, req.type)
        report = await jnao_get_report(record_id)
        assessment_id = None
        conflict = False
        locked = False
        lock_msg = None
        current_talent = None
        if req.child_user_id:
            user = db.get(ChildUser, req.child_user_id)
            if user and user.profile_json:
                current_talent = (user.profile_json or {}).get("talent_primary")
            row = assessment_service.save_assessment(
                db,
                child_user_id=req.child_user_id,
                jnao_record_id=str(record_id),
                answer_bitstring=req.answer,
                test_type=req.type,
                report=report,
            )
            assessment_id = row.id
            conflict = getattr(row, "_talent_conflict", False)
            locked = getattr(row, "_talent_locked", False)
            if locked:
                lock_msg = assessment_service.TALENT_LOCK_MSG
            if conflict and user:
                db.refresh(user)
                current_talent = (user.profile_json or {}).get("talent_primary") or current_talent
        return {
            "code": 1,
            "data": report,
            "assessment_id": assessment_id,
            "talent_conflict": conflict,
            "talent_locked": locked,
            "lock_message": lock_msg,
            "current_talent": current_talent,
        }
    except Exception as e:
        raise HTTPException(502, str(e)) from e


@router.post("/assessment")
async def save_assessment_endpoint(
    req: ReportRequest,
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """测评完成并落库（需 user_id / X-Child-User-Id）"""
    try:
        record_id = await jnao_submit(req.answer, req.uid, req.type)
        report = await jnao_get_report(record_id)
        row = assessment_service.save_assessment(
            db,
            child_user_id=child_user_id,
            jnao_record_id=str(record_id),
            answer_bitstring=req.answer,
            test_type=req.type,
            report=report,
        )
        user = db.get(ChildUser, child_user_id)
        current = (user.profile_json or {}).get("talent_primary", "") if user else ""
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
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
    limit: int = 30,
):
    return {"items": assessment_service.list_assessments(db, child_user_id, limit)}


@router.get("/assessment/latest", response_model=AssessmentOut)
def latest_assessment(
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """最新测评；无 JNAO 记录时若有引导页自选天赋也返回 200"""
    assessment_service.repair_onboarding_talent(db, child_user_id)
    row = assessment_service.get_latest_assessment(db, child_user_id)
    if row:
        return AssessmentOut(
            id=row.id,
            child_user_id=row.child_user_id,
            talent_primary=row.talent_primary,
            talent_tag=row.talent_tag,
            talent_code=row.talent_code,
            assessed_at=row.assessed_at.isoformat() if row.assessed_at else None,
            jnao_record_id=row.jnao_record_id,
            talent_source="assessment",
        )
    eff = assessment_service.resolve_effective_talent(db, child_user_id)
    if eff and eff.get("talent_code"):
        user = db.get(ChildUser, child_user_id)
        onboarding = {}
        if user and isinstance(user.profile_json, dict):
            onboarding = user.profile_json.get("onboarding") or {}
        return AssessmentOut(
            id=0,
            child_user_id=child_user_id,
            talent_primary=eff.get("talent_primary"),
            talent_tag=eff.get("talent_tag"),
            talent_code=eff.get("talent_code"),
            assessed_at=onboarding.get("completed_at"),
            jnao_record_id=None,
            talent_source=eff.get("talent_source"),
        )
    raise HTTPException(404, "尚未完成天赋测评")


@router.get("/assessment/{assessment_id}")
def get_assessment(
    assessment_id: int,
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    row = assessment_service.get_assessment_by_id(db, assessment_id, child_user_id)
    if not row:
        raise HTTPException(404, "测评记录不存在")
    report = row.report_json or {}
    return {
        "code": 1,
        "data": report,
        "assessment_id": row.id,
        "talent_primary": row.talent_primary,
        "assessed_at": row.assessed_at.isoformat() if row.assessed_at else None,
    }


@router.delete("/assessment/{assessment_id}")
def delete_assessment_endpoint(
    assessment_id: int,
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """删除历史测评（归档后从主表移除，定时全库备份保留副本）"""
    try:
        return assessment_service.delete_assessment(db, assessment_id, child_user_id)
    except assessment_service.AssessmentError as e:
        raise HTTPException(e.status_code, e.message) from e
