"""在线咨询 WebSocket 连接枢纽 — 按家长 user_id 推送；群聊扇出给全体成员。"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Iterable

from fastapi import WebSocket

logger = logging.getLogger("jnao.consult.ws")


class ConsultWsHub:
    def __init__(self) -> None:
        self._conns: dict[int, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, user_id: int, ws: WebSocket) -> None:
        self._loop = asyncio.get_running_loop()
        await ws.accept()
        self._conns[user_id].add(ws)
        logger.info("consult ws connect uid=%s n=%s", user_id, len(self._conns[user_id]))

    def disconnect(self, user_id: int, ws: WebSocket) -> None:
        room = self._conns.get(user_id)
        if not room:
            return
        room.discard(ws)
        if not room:
            self._conns.pop(user_id, None)
        logger.info("consult ws disconnect uid=%s", user_id)

    async def _broadcast(self, user_id: int, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._conns.get(user_id, ())):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    def publish(self, user_id: int, payload: dict[str, Any]) -> None:
        if user_id < 1:
            return
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        try:
            asyncio.run_coroutine_threadsafe(self._broadcast(user_id, payload), loop)
        except Exception:
            logger.exception("consult ws publish failed uid=%s", user_id)

    def publish_many(self, user_ids: Iterable[int], payload: dict[str, Any]) -> None:
        seen: set[int] = set()
        for uid in user_ids:
            if uid and uid not in seen:
                seen.add(uid)
                self.publish(uid, payload)

    def online_count(self, user_id: int) -> int:
        return len(self._conns.get(user_id, ()))

    def online_among(self, user_ids: Iterable[int]) -> int:
        return sum(1 for uid in user_ids if uid and self.online_count(uid) > 0)


hub = ConsultWsHub()


def publish_message_new(*, parent_user_id: int, conversation_id: int, message: dict) -> None:
    hub.publish(
        parent_user_id,
        {
            "type": "message.new",
            "conversation_id": conversation_id,
            "message": message,
        },
    )


def publish_message_to_users(
    *,
    user_ids: Iterable[int],
    conversation_id: int,
    message: dict,
) -> None:
    hub.publish_many(
        user_ids,
        {
            "type": "message.new",
            "conversation_id": conversation_id,
            "message": message,
        },
    )


def publish_board_updated(*, parent_user_id: int, channel_code: str, post: dict) -> None:
    hub.publish(
        parent_user_id,
        {
            "type": "board.updated",
            "channel_code": channel_code,
            "post": post,
        },
    )
