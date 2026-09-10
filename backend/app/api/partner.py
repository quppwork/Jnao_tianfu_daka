"""合作方开放接口 — API Key 鉴权"""

from __future__ import annotations

import hmac
import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.biz_log import biz_event
from app.schemas.auth import PartnerJinnaoRegisterRequest, PartnerJinnaoRegisterResponse
from app.services.member_registry_service import CHANNEL_JINNAO, REGISTER_SOURCE_JINNAO
from app.services.parent_profile_service import register_parent_from_partner

logger = logging.getLogger("jnao")

router = APIRouter(prefix="/api/partner", tags=["partner"])


def _jinnao_api_key() -> str:
    return (os.getenv("JINNAO_PARTNER_API_KEY") or "").strip()


def require_jinnao_api_key(x_api_key: str | None = Header(None, alias="X-Api-Key")) -> None:
    expected = _jinnao_api_key()
    if not expected:
        raise HTTPException(503, "劲脑合作接口未配置（缺少 JINNAO_PARTNER_API_KEY）")
    provided = (x_api_key or "").strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(401, "无效的 API Key")


@router.post(
    "/jinnao/register-parent",
    response_model=PartnerJinnaoRegisterResponse,
    dependencies=[Depends(require_jinnao_api_key)],
)
def jinnao_register_parent(
    req: PartnerJinnaoRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """劲脑侧免短信注册家长账号。

    保留短信注册的其他必填参数（phone / real_name / nickname / password），
    不校验短信验证码；来源记为「劲脑」。返回本系统 user_id 供对方关联。
    若手机号已注册，返回已有 user_id 且 created=false。
    """
    user, created = register_parent_from_partner(
        db,
        phone=req.phone.strip(),
        nickname=req.nickname,
        real_name=req.real_name,
        password=req.password,
        register_channel=CHANNEL_JINNAO,
        register_source=REGISTER_SOURCE_JINNAO,
        partner_ref=req.partner_ref,
    )
    biz_event(
        "partner.jinnao.register_parent",
        uid=user.id,
        role="parent",
        created=created,
        phone_tail=(user.parent_phone or "")[-4:],
        partner_ref=(req.partner_ref or "")[:32] or None,
        ip=getattr(request.client, "host", None) if request.client else None,
    )
    logger.info(
        "partner jinnao register-parent user_id=%s created=%s",
        user.id,
        created,
    )
    return PartnerJinnaoRegisterResponse(
        user_id=user.id,
        parent_phone=user.parent_phone or "",
        nickname=user.nickname or "",
        register_channel=CHANNEL_JINNAO,
        register_source=REGISTER_SOURCE_JINNAO,
        created=created,
        partner_ref=(req.partner_ref or None),
    )
