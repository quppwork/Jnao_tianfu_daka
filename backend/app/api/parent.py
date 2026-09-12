"""家长端 API — 孩子账号分配与管理 + 大宇对话（知识库）"""

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_user, get_db
from app.core.cache import invalidate_user_profile
from app.core.biz_log import biz_event
from app.core.rate_limit import check_guide_chat_limits
from app.core.session_cookie import set_session_cookie
from app.core.sse import SSE_HEADERS, emit_event_stream, sse_done, sse_json
from app.schemas.auth import (
    ChildDetailResponse,
    ChildSummaryOut,
    CreateChildRequest,
    ParentChildrenResponse,
    ParentProfileResponse,
    ParentProfileUpdateRequest,
    ParentQuotaResponse,
    UpdateChildRequest,
)
from app.services import parent_dashboard_service, parent_guide_service, parent_service
from app.services.parent_profile_service import parent_profile_to_dict, update_parent_profile, assert_parent_account_ready

router = APIRouter(prefix="/api/parent", tags=["parent"])


class ParentGuideChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: int | None = Field(None, ge=1)
    child_id: int | None = Field(None, ge=1, description="关注的孩子；默认第一个绑定孩子")


def _require_parent_id(
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> int:
    from app.services import auth_service
    from app.core.biz_log import bind_user

    user = auth_service.get_child_user(db, user_id)
    if not user or user.role != auth_service.ROLE_PARENT:
        raise HTTPException(403, "需要家长账号")
    bind_user(user_id, role=auth_service.ROLE_PARENT)
    return user_id


@router.get("/profile", response_model=ParentProfileResponse)
def get_profile(
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    from app.services import auth_service

    user = auth_service.get_child_user(db, user_id)
    return ParentProfileResponse(**parent_profile_to_dict(user, db=db))


@router.put("/profile", response_model=ParentProfileResponse)
def put_profile(
    req: ParentProfileUpdateRequest,
    response: Response,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    user, new_token = update_parent_profile(
        db,
        user_id,
        nickname=req.nickname,
        real_name=req.real_name,
        password=req.password,
        old_password=req.old_password,
        require_password=req.require_password,
    )
    if new_token:
        from app.services import auth_service

        set_session_cookie(response, new_token, role=auth_service.ROLE_PARENT)
    invalidate_user_profile(user_id)
    return ParentProfileResponse(**parent_profile_to_dict(user, session_token=new_token, db=db))


@router.get("/quota", response_model=ParentQuotaResponse)
def get_quota(user_id: int = Depends(_require_parent_id), db: Session = Depends(get_db)):
    """预留：查询家长可分配的孩子名额"""
    return parent_service.get_quota(db, user_id)


@router.get("/children", response_model=ParentChildrenResponse)
def list_children(user_id: int = Depends(_require_parent_id), db: Session = Depends(get_db)):
    items = parent_service.list_children(db, user_id)
    return ParentChildrenResponse(children=[ChildSummaryOut(**c) for c in items])


@router.post("/children", response_model=ChildSummaryOut)
def create_child(
    req: CreateChildRequest,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    from app.services import auth_service

    parent = auth_service.get_child_user(db, user_id)
    assert_parent_account_ready(parent, db)
    child = parent_service.create_child(
        db,
        user_id,
        login_name=req.login_name,
        nickname=req.nickname,
        password=req.password,
        grade=req.grade,
        age=req.age,
        region=req.region,
    )
    from app.services import auth_service
    from app.core.biz_log import biz_event

    invalidate_user_profile(child.id)
    biz_event(
        "parent.child_create",
        result="ok",
        uid=user_id,
        role="parent",
        child_id=child.id,
        login_name=child.login_name or "-",
    )
    return ChildSummaryOut(**auth_service.child_summary(db, child))


@router.put("/children/{child_id}", response_model=ChildSummaryOut)
def update_child(
    child_id: int,
    req: UpdateChildRequest,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    child = parent_service.update_child(
        db,
        user_id,
        child_id,
        nickname=req.nickname,
        password=req.password,
        grade=req.grade,
        age=req.age,
        region=req.region,
    )
    from app.services import auth_service

    invalidate_user_profile(child.id)
    from app.core.biz_log import biz_event

    biz_event(
        "parent.child_update",
        result="ok",
        uid=user_id,
        role="parent",
        child_id=child.id,
    )
    return ChildSummaryOut(**auth_service.child_summary(db, child))


@router.delete("/children/{child_id}")
def delete_child(
    child_id: int,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    parent_service.delete_child(db, user_id, child_id)
    from app.core.biz_log import biz_event

    biz_event(
        "parent.child_delete",
        result="ok",
        uid=user_id,
        role="parent",
        child_id=child_id,
    )
    return {"ok": True}


@router.get("/children/{child_id}/summary", response_model=ChildDetailResponse)
def child_summary(
    child_id: int,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    """预留：家长查看单个孩子信息摘要"""
    data = parent_service.get_child_detail(db, user_id, child_id)
    return ChildDetailResponse(**data)


@router.get("/children/{child_id}/dashboard")
async def child_dashboard(
    child_id: int,
    insight: bool = True,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    """孩子训练看板：周时长/有效率/XP/冲段焦虑 + 大宇解读（豆包 one-shot）。"""
    from app.services.usage_recorder import bind_usage_feature

    bind_usage_feature("parent_dashboard")
    return await parent_dashboard_service.get_dashboard_with_insight(
        db, user_id, child_id, with_insight=insight
    )


@router.get("/assessments/history")
def parent_assessment_history(
    child_id: int | None = None,
    limit: int = 50,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    """家长查看绑定孩子的测试记录（天赋测评历史）。"""
    from app.services import assessment_service

    try:
        items = assessment_service.list_assessments_for_parent(
            db, user_id, child_id=child_id, limit=limit
        )
    except assessment_service.AssessmentError as e:
        raise HTTPException(e.status_code, e.message) from e
    return {"items": items}


@router.delete("/assessments/{assessment_id}")
def parent_delete_assessment(
    assessment_id: int,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    """家长删除绑定孩子的一条测评记录。"""
    from app.db.models import TalentAssessment
    from app.services import assessment_service

    row = db.get(TalentAssessment, assessment_id)
    if not row:
        raise HTTPException(404, "测评记录不存在")
    parent_service.get_child_detail(db, user_id, row.child_user_id)
    try:
        return assessment_service.delete_assessment(db, assessment_id, row.child_user_id)
    except assessment_service.AssessmentError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/guide/session")
def parent_guide_session(
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    return parent_guide_service.load_session_payload(db, user_id)


@router.post("/guide/chat")
async def parent_guide_chat(
    req: ParentGuideChatRequest,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    check_guide_chat_limits(user_id)
    from app.services.usage_recorder import bind_usage_feature

    bind_usage_feature("parent_guide")
    biz_event(
        "parent.guide.chat",
        result="start",
        uid=user_id,
        role="parent",
        session_id=req.session_id,
        msg_len=len(req.message or ""),
    )
    result = await parent_guide_service.chat(
        db,
        user_id,
        req.message,
        session_id=req.session_id,
        child_id=req.child_id,
    )
    biz_event("parent.guide.chat", result="ok", uid=user_id, role="parent")
    return result


@router.post("/guide/chat/stream")
async def parent_guide_chat_stream(
    req: ParentGuideChatRequest,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    check_guide_chat_limits(user_id)
    from app.services.usage_recorder import bind_usage_feature

    bind_usage_feature("parent_guide")
    biz_event(
        "parent.guide.chat_stream",
        result="start",
        uid=user_id,
        role="parent",
        session_id=req.session_id,
        msg_len=len(req.message or ""),
    )

    async def events():
        try:
            async for chunk in emit_event_stream(
                parent_guide_service.chat_stream(
                    db,
                    user_id,
                    req.message,
                    session_id=req.session_id,
                    child_id=req.child_id,
                )
            ):
                yield chunk
            biz_event("parent.guide.chat_stream", result="ok", uid=user_id, role="parent")
        except HTTPException as e:
            biz_event("parent.guide.chat_stream", result="error", uid=user_id, role="parent")
            yield sse_json({"type": "error", "message": e.detail if isinstance(e.detail, str) else "请求失败"})
            yield sse_done()
        except Exception:  # noqa: BLE001
            biz_event("parent.guide.chat_stream", result="error", uid=user_id, role="parent")
            yield sse_json({"type": "error", "message": "对话暂时不可用，请稍后再试"})
            yield sse_done()

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)
