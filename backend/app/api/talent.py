"""天赋测试 API — JNAO 报告代理 + 测评落库"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_child_user_id, get_db
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
        if req.child_user_id:
            row = assessment_service.save_assessment(
                db,
                child_user_id=req.child_user_id,
                jnao_record_id=str(record_id),
                answer_bitstring=req.answer,
                test_type=req.type,
                report=report,
            )
            assessment_id = row.id
        return {"code": 1, "data": report, "assessment_id": assessment_id}
    except Exception as e:
        raise HTTPException(502, str(e)) from e


@router.post("/assessment")
async def save_assessment_endpoint(
    req: ReportRequest,
    child_user_id: int = Depends(get_child_user_id),
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
        return {
            "code": 1,
            "data": report,
            "assessment_id": row.id,
            "talent_code": row.talent_code,
            "talent_tag": row.talent_tag,
        }
    except Exception as e:
        raise HTTPException(502, str(e)) from e


@router.get("/assessment/history")
def assessment_history(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
    limit: int = 30,
):
    return {"items": assessment_service.list_assessments(db, child_user_id, limit)}


@router.get("/assessment/latest", response_model=AssessmentOut)
def latest_assessment(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    row = assessment_service.get_latest_assessment(db, child_user_id)
    if not row:
        raise HTTPException(404, "尚未完成天赋测评")
    return AssessmentOut(
        id=row.id,
        child_user_id=row.child_user_id,
        talent_primary=row.talent_primary,
        talent_tag=row.talent_tag,
        talent_code=row.talent_code,
        assessed_at=row.assessed_at.isoformat() if row.assessed_at else None,
        jnao_record_id=row.jnao_record_id,
    )


@router.get("/assessment/{assessment_id}")
def get_assessment(
    assessment_id: int,
    child_user_id: int = Depends(get_child_user_id),
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
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    """删除历史测评（归档后从主表移除，定时全库备份保留副本）"""
    try:
        return assessment_service.delete_assessment(db, assessment_id, child_user_id)
    except assessment_service.AssessmentError as e:
        raise HTTPException(e.status_code, e.message) from e
