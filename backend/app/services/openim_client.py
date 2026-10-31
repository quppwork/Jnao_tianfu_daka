"""OpenIM 服务端 REST 适配层。

文档: https://docs.openim.io/platform-api/prepare-to-use-api
密钥与地址由 CONSULT_IM_* 注入；未配齐时所有调用返回 None / 抛配置错误。
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

import httpx

logger = logging.getLogger("jnao.consult.openim")

# OpenIM contentType：101=文本；sessionType：1=单聊 3=群聊
CONTENT_TEXT = 101
SESSION_SINGLE = 1
SESSION_GROUP = 3
PLATFORM_WEB = 5  # Web；客户端登录用


def load_openim_config() -> dict[str, Any]:
    return {
        "provider": (os.getenv("CONSULT_IM_PROVIDER") or "openim").strip().lower(),
        "api_url": (os.getenv("CONSULT_IM_API_URL") or "").strip().rstrip("/"),
        "secret": (os.getenv("CONSULT_IM_SECRET") or "").strip(),
        "admin_user": (os.getenv("CONSULT_IM_ADMIN_USER") or "imAdmin").strip(),
        "callback_token": (os.getenv("CONSULT_IM_CALLBACK_TOKEN") or "").strip(),
        # Bot / 系统通知账号（需在 OpenIM 预先注册或由 ensure_bot_user 创建）
        "bot_user_id": (os.getenv("CONSULT_IM_BOT_USER_ID") or "jnao_bot_dayu").strip(),
        "timeout": float(os.getenv("CONSULT_IM_TIMEOUT", "10")),
    }


def is_openim_ready() -> bool:
    cfg = load_openim_config()
    return (
        cfg["provider"] == "openim"
        and bool(cfg["api_url"])
        and bool(cfg["secret"])
    )


def parent_im_user_id(parent_user_id: int) -> str:
    return f"jnao_p_{parent_user_id}"


def advisor_im_user_id(advisor_user_id: int) -> str:
    return f"jnao_a_{advisor_user_id}"


def dm_conversation_id(a: str, b: str) -> str:
    """单聊业务侧约定 ID（OpenIM 单聊会话由双方 userID 推导，此处仅作业务落库用）。"""
    x, y = sorted([a, b])
    return f"si_{x}_{y}"


class OpenIMClient:
    """管理端调用：管理员 token 缓存 + 发消息 / 发用户 token。"""

    def __init__(self) -> None:
        self._admin_token: str | None = None
        self._admin_expire_at: float = 0.0

    def _cfg(self) -> dict[str, Any]:
        cfg = load_openim_config()
        if not is_openim_ready():
            raise RuntimeError(
                "OpenIM 未配置：请填 CONSULT_IM_API_URL + CONSULT_IM_SECRET"
                "（CONSULT_IM_PROVIDER=openim）"
            )
        return cfg

    def _headers(self, token: str | None = None) -> dict[str, str]:
        h = {
            "Content-Type": "application/json; charset=utf-8",
            "operationID": uuid.uuid4().hex,
        }
        if token:
            h["token"] = token
        return h

    def _post(self, path: str, body: dict, *, token: str | None = None) -> dict[str, Any]:
        cfg = self._cfg()
        url = f"{cfg['api_url']}{path}"
        with httpx.Client(timeout=cfg["timeout"]) as client:
            r = client.post(url, json=body, headers=self._headers(token))
            r.raise_for_status()
            data = r.json()
        # OpenIM 成功一般为 errCode == 0
        code = data.get("errCode")
        if code is not None and int(code) != 0:
            raise RuntimeError(
                f"OpenIM {path} errCode={code} errMsg={data.get('errMsg')}"
            )
        return data

    def get_admin_token(self, *, force: bool = False) -> str:
        now = time.time()
        if (
            not force
            and self._admin_token
            and now < self._admin_expire_at - 60
        ):
            return self._admin_token
        cfg = self._cfg()
        data = self._post(
            "/auth/get_admin_token",
            {"userID": cfg["admin_user"], "secret": cfg["secret"]},
            token=None,
        )
        payload = data.get("data") or {}
        token = payload.get("token") or ""
        if not token:
            raise RuntimeError("OpenIM get_admin_token 未返回 token")
        expire = int(payload.get("expireTimeSeconds") or 86400)
        self._admin_token = token
        self._admin_expire_at = now + expire
        return token

    def get_user_token(self, user_id: str, *, platform_id: int = PLATFORM_WEB) -> dict[str, Any]:
        admin = self.get_admin_token()
        data = self._post(
            "/auth/get_user_token",
            {"platformID": platform_id, "userID": user_id},
            token=admin,
        )
        return data.get("data") or {}

    def ensure_user(
        self,
        user_id: str,
        *,
        nickname: str,
        face_url: str = "",
    ) -> None:
        """注册用户（已存在则忽略）。API: /user/user_register"""
        admin = self.get_admin_token()
        try:
            self._post(
                "/user/user_register",
                {
                    "users": [
                        {
                            "userID": user_id,
                            "nickname": nickname or user_id,
                            "faceURL": face_url or "",
                        }
                    ]
                },
                token=admin,
            )
        except RuntimeError as e:
            # 用户已存在等业务错误：记录后继续（具体 errCode 随版本变化）
            logger.info("openim ensure_user %s: %s", user_id, e)

    def create_group(
        self,
        *,
        group_id: str,
        group_name: str,
        owner_user_id: str,
        member_user_ids: list[str],
    ) -> str:
        """创建群。API: /group/create_group。返回 groupID。"""
        admin = self.get_admin_token()
        members = [{"userID": uid, "roleLevel": 20} for uid in member_user_ids]
        data = self._post(
            "/group/create_group",
            {
                "ownerUserID": owner_user_id,
                "groupInfo": {
                    "groupID": group_id,
                    "groupName": group_name,
                    "groupType": 2,
                },
                "memberUserIDs": [m["userID"] for m in members],
            },
            token=admin,
        )
        info = (data.get("data") or {}).get("groupInfo") or {}
        return info.get("groupID") or group_id

    def send_text(
        self,
        *,
        send_id: str,
        text: str,
        recv_id: str = "",
        group_id: str = "",
        session_type: int = SESSION_SINGLE,
        nickname: str = "",
    ) -> str | None:
        """服务端代发文本；返回 serverMsgID。"""
        admin = self.get_admin_token()
        body: dict[str, Any] = {
            "sendID": send_id,
            "recvID": recv_id,
            "groupID": group_id,
            "senderNickname": nickname or send_id,
            "senderPlatformID": 10,
            "content": {"content": text},
            "contentType": CONTENT_TEXT,
            "sessionType": session_type,
            "isOnlineOnly": False,
            "notOfflinePush": False,
        }
        data = self._post("/msg/send_msg", body, token=admin)
        payload = data.get("data") or {}
        return payload.get("serverMsgID") or payload.get("clientMsgID")


_client: OpenIMClient | None = None


def get_openim_client() -> OpenIMClient:
    global _client
    if _client is None:
        _client = OpenIMClient()
    return _client
