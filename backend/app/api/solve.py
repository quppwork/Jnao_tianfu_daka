"""拍题解答 API — POST /api/solve/photo（SSE）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_student, get_db
from app.core.rate_limit import check_rate_limit
from app.core.sse import SSE_HEADERS, emit_event_stream, sse_done, sse_json

router = APIRouter(prefix="/api/solve", tags=["solve"])


@router.post("/photo")
async def solve_photo(
    image: UploadFile = File(...),
    subject_hint: str | None = Form(None),
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """拍题：压缩 → OCR → 领域 Profile → 题库优先 → RAG/LLM（SSE）。"""
    del db
    check_rate_limit(f"solve:{child_user_id}", max_calls=20, window_sec=60)
    from app.agents.solve.runner import run_solve_photo_stream
    from app.services.usage_recorder import bind_usage_feature

    bind_usage_feature("solve")
    raw = await image.read()
    if not raw or len(raw) < 32:
        raise HTTPException(400, "图片无效或过小")
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(400, "图片过大（上限 12MB）")

    async def events():
        try:
            async for chunk in emit_event_stream(
                run_solve_photo_stream(
                    raw,
                    user_id=child_user_id,
                    subject_hint=subject_hint,
                    filename=image.filename or "photo.jpg",
                )
            ):
                yield chunk
        except Exception as e:
            yield sse_json({"type": "error", "message": str(e)[:300]})
            yield sse_done()

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/photo/sync")
async def solve_photo_sync(
    image: UploadFile = File(...),
    subject_hint: str | None = Form(None),
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """非流式聚合（便于联调）。"""
    del db
    check_rate_limit(f"solve_sync:{child_user_id}", max_calls=20, window_sec=60)
    from app.agents.solve.runner import run_solve_photo
    from app.services.usage_recorder import bind_usage_feature

    bind_usage_feature("solve")
    raw = await image.read()
    if not raw or len(raw) < 32:
        raise HTTPException(400, "图片无效或过小")
    result = await run_solve_photo(
        raw,
        user_id=child_user_id,
        subject_hint=subject_hint,
        filename=image.filename or "photo.jpg",
    )
    # 学业规划未就绪：仍 200，前端展示引导去补规划（OCR 可保存）
    if result.get("source") == "need_academic_plan":
        return result
    if result.get("ok") is False:
        raise HTTPException(400, result.get("error") or "解答失败")
    return result
