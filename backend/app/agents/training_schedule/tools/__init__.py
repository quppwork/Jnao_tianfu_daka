"""排课 Agent 工具注册表 — 只读 + 提交草案；禁止写 Tier/OSS/DB。"""

from __future__ import annotations

import json
from typing import Any, Callable

from sqlalchemy.orm import Session

ToolFn = Callable[[Session, int, dict], Any]

TOOL_REGISTRY: dict[str, ToolFn] = {}

# OpenAI / Ark tools schema
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_curriculum_overview",
            "description": "全课表与各阶重点：全技能、各 tier 可用/权重/key·secondary、学段标注",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_schedule_context",
            "description": "学生排课上下文：时长、软预算 slot_budget、天赋、年级、tier、技能档、节奏",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_skills",
            "description": "今日可排技能 + 本阶重点 + 未解锁预览（草案只能写 selectable_now）",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_training_history",
            "description": "近几日已练技能摘要，用于避免总推同一技能",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "回顾天数，默认 7",
                    }
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_checkin_skill_summary",
            "description": "近史打卡按技能摘要：次数、达标倾向、用时/正确率/配合度均值（无晋级计数）",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "回顾天数，默认 14",
                    }
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_training_rhythm",
            "description": "连打天数、距上次打卡间隔、近史方案项完成比例",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "回顾天数，默认 14",
                    }
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_slot_budget_hint",
            "description": "今日必修项数软预算（按时长档；非标准方案名单）",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_skill_draft",
            "description": (
                "提交今日技能推荐顺序与简短理由（最终一步；"
                "skills 只能含 selectable_now；长度建议约等于 slot_budget；可按画像重复弱项）"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "skills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "推荐技能名顺序（可重复同一技能；按画像自主排，勿抄标准方案）",
                    },
                    "reason": {
                        "type": "string",
                        "description": (
                            "中文简述为何这样排（结合本阶重点/打卡质量/节奏；"
                            "1～3 句，勿写晋级公式）"
                        ),
                    },
                },
                "required": ["skills", "reason"],
                "additionalProperties": False,
            },
        },
    },
]


def register(name: str):
    def deco(fn: ToolFn) -> ToolFn:
        TOOL_REGISTRY[name] = fn
        return fn
    return deco


def list_tools() -> list[str]:
    from app.agents.training_schedule.tools import (  # noqa: F401
        available_skills,
        checkin_skill_summary,
        context,
        curriculum_overview,
        propose_draft,
        recent_history,
        rule_slot_hint,
        training_rhythm,
    )

    return sorted(TOOL_REGISTRY.keys())


def openai_tool_schemas() -> list[dict[str, Any]]:
    list_tools()
    return list(TOOL_SCHEMAS)


def call_tool(db: Session, child_user_id: int, name: str, args: dict | None = None) -> Any:
    if name not in TOOL_REGISTRY:
        list_tools()
    fn = TOOL_REGISTRY.get(name)
    if not fn:
        raise KeyError(f"unknown training_schedule tool: {name}")
    return fn(db, child_user_id, args or {})


def tool_result_text(name: str, result: Any) -> str:
    try:
        body = json.dumps(result, ensure_ascii=False, default=str)
    except TypeError:
        body = str(result)
    if len(body) > 4000:
        body = body[:4000] + "…"
    return body
