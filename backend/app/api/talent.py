"""天赋测试 API — JNAO 报告代理"""

from fastapi import APIRouter, HTTPException, Query

from app.services.jnao_client import jnao_submit, jnao_get_report
from app.models.requests import ReportRequest

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
        raise HTTPException(502, f"JNAO 提交失败: {e}")


@router.get("/jnao/report/{record_id}")
async def jnao_report(record_id: str):
    """代理获取 JNAO 报告 JSON"""
    try:
        report = await jnao_get_report(record_id)
        return {"code": 1, "data": report}
    except Exception as e:
        raise HTTPException(502, f"JNAO 报告获取失败: {e}")


@router.post("/report")
async def talent_report(req: ReportRequest):
    """提交答案 + 获取报告（一步完成）"""
    try:
        record_id = await jnao_submit(req.answer, req.uid, req.type)
        report = await jnao_get_report(record_id)
        return {"code": 1, "data": report}
    except Exception as e:
        raise HTTPException(502, str(e))
