"""LLM 路由 — 内核只保留 PROFILES，不把业务 loop 收进来。"""

from __future__ import annotations

from typing import Any

PROFILES: dict[str, dict[str, Any]] = {
    "consult": {
        "system": "你是家长咨询助手大宇。优先用 retrieve_kb；不要编造政策价格。",
        "feature": "consult",
        "max_tokens": 700,
        "timeout": 45,
    },
    "guide": {
        "system": "你是训练教练。用只读工具核对事实，再简短中文回答。",
        "feature": "guide",
        "max_tokens": 500,
        "timeout": 30,
    },
    "parent_guide": {
        "system": "你面向家长。用看板/知识库工具，不要编造孩子分数。",
        "feature": "parent_guide",
        "max_tokens": 420,
        "timeout": 30,
    },
    "qa": {
        "system": "你是学科答疑助手。具体解题可提示去答疑页；可用检索与苏格拉底提示。",
        "feature": "qa",
        "max_tokens": 900,
        "timeout": 45,
    },
    "teacher": {
        "system": "你是教师助手。只读学院目录与学员进度；写课程必须等待确认。",
        "feature": "teacher",
        "max_tokens": 500,
        "timeout": 30,
    },
    "academy": {
        "system": "你是学院角色。按角色卡口吻说一句口语，不要旁白。",
        "feature": "academy",
        "max_tokens": 120,
        "timeout": 25,
        "disable_thinking": True,
    },
    "harness": {
        "system": "你是 Harness 探测助手。",
        "feature": "harness",
        "max_tokens": 400,
        "timeout": 30,
    },
}


def profile_system(profile: str) -> str:
    row = PROFILES.get(profile) or PROFILES["harness"]
    return str(row.get("system") or "")


async def complete(
    profile: str,
    *,
    system_prompt: str | None = None,
    user_message: str,
    history: list[dict] | None = None,
    **overrides: Any,
) -> str | None:
    """按 profile 默认参数调 DeepSeek；业务可覆盖 max_tokens / feature。"""
    from app.services.doubao_client import chat_completion

    cfg = dict(PROFILES.get(profile) or PROFILES["harness"])
    cfg.update({k: v for k, v in overrides.items() if v is not None})
    return await chat_completion(
        system_prompt=system_prompt or str(cfg.get("system") or ""),
        user_message=user_message,
        history=history or [],
        max_tokens=int(cfg.get("max_tokens") or 400),
        timeout=float(cfg.get("timeout") or 30),
        feature=str(cfg.get("feature") or profile),
        disable_thinking=bool(cfg.get("disable_thinking")),
    )


async def complete_stream(
    profile: str,
    *,
    messages: list[dict],
    **overrides: Any,
):
    """按 profile 流式；无 tools。"""
    from app.services.doubao_client import chat_completion_messages_stream

    cfg = dict(PROFILES.get(profile) or PROFILES["harness"])
    cfg.update({k: v for k, v in overrides.items() if v is not None})
    async for tok in chat_completion_messages_stream(
        messages=messages,
        max_tokens=int(cfg.get("max_tokens") or 400),
        feature=str(cfg.get("feature") or profile),
    ):
        yield tok
