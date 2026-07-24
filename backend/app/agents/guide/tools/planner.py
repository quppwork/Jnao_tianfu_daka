"""工具目录 + 调度：启发式优先，可选 LLM JSON 选工具。"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.agents.guide.tools import call_tool, list_tools
from app.core.logger import get_logger

logger = get_logger("guide.tools")

MAX_TOOLS_PER_TURN = 2
MAX_TOOL_RESULT_CHARS = 1800

# name -> (说明, 关键词)
TOOL_SPECS: dict[str, tuple[str, tuple[str, ...]]] = {
    "get_profile": (
        "画像与天赋（昵称/年级/是否测评）",
        ("天赋", "测评", "画像", "年级", "我是谁", "什么者"),
    ),
    "get_today_plan": (
        "今日训练方案快照（是否开始/完成几项）",
        ("今天练", "今日训练", "练了吗", "完成几项", "今天的方案", "今日方案"),
    ),
    "get_checkin_timeline": (
        "近期打卡时间线摘要",
        ("打卡", "上周", "最近几天", "练了几次", "多久没", "历史", "时间线"),
    ),
    "get_skill_progress": (
        "分技能 Tier 进度",
        ("进度", "tier", "Tier", "技能", "哪项弱", "哪项强", "等级"),
    ),
    "suggest_next_action": (
        "建议下一步入口（talent/train/qa/growth）",
        ("接下来", "下一步", "该做什么", "建议去", "做什么好"),
    ),
}

PLANNER_SYSTEM = (
    "你是首页引导的工具调度器。根据用户问题决定是否调用只读工具。\n"
    "只输出一行 JSON，不要解释，格式：\n"
    '{"tools":[{"name":"工具名","args":{}}]}\n'
    '不需要工具时：{"tools":[]}\n'
    "最多选 2 个。可用工具：\n"
    + "\n".join(f"- {n}: {desc}" for n, (desc, _) in TOOL_SPECS.items())
)


def plan_tools_heuristic(message: str) -> list[dict[str, Any]]:
    """关键词启发式选工具；稳定、可测、零 LLM 成本。"""
    text = (message or "").strip().lower()
    if not text:
        return []
    picks: list[dict[str, Any]] = []
    for name, (_desc, keys) in TOOL_SPECS.items():
        if any(k.lower() in text for k in keys):
            args: dict[str, Any] = {}
            if name == "get_checkin_timeline":
                args["limit"] = 14
            picks.append({"name": name, "args": args})
        if len(picks) >= MAX_TOOLS_PER_TURN:
            break
    return picks


def _parse_tools_json(raw: str) -> list[dict[str, Any]]:
    text = (raw or "").strip()
    if not text:
        return []
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    tools = data.get("tools") if isinstance(data, dict) else None
    if not isinstance(tools, list):
        return []
    allowed = set(TOOL_SPECS)
    out: list[dict[str, Any]] = []
    for item in tools:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if name not in allowed:
            continue
        args = item.get("args") if isinstance(item.get("args"), dict) else {}
        out.append({"name": name, "args": args})
        if len(out) >= MAX_TOOLS_PER_TURN:
            break
    return out


async def plan_tools_llm(message: str) -> list[dict[str, Any]]:
    """LLM JSON 调度；失败返回 []。"""
    from app.services.doubao_client import chat_completion, is_configured

    if not is_configured():
        return []
    list_tools()
    try:
        raw = await chat_completion(
            system_prompt=PLANNER_SYSTEM,
            user_message=message,
            history=None,
            max_tokens=120,
            timeout=8,
        )
    except Exception as e:
        logger.warning(f"tool planner LLM failed: {e}")
        return []
    return _parse_tools_json(raw or "")


async def plan_tools(
    message: str,
    *,
    use_llm_fallback: bool = True,
) -> list[dict[str, Any]]:
    picks = plan_tools_heuristic(message)
    if picks or not use_llm_fallback:
        return picks
    return await plan_tools_llm(message)


def execute_tools(
    db: Session,
    child_user_id: int,
    picks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    """执行工具，返回 (audit, 注入用文本)。"""
    list_tools()
    audit: list[dict[str, Any]] = []
    blocks: list[str] = []
    for pick in picks[:MAX_TOOLS_PER_TURN]:
        name = pick["name"]
        args = pick.get("args") or {}
        try:
            result = call_tool(db, child_user_id, name, args)
            ok = True
            err = None
        except Exception as e:
            logger.warning(f"tool {name} failed uid={child_user_id}: {e}")
            result = {"error": str(e)}
            ok = False
            err = str(e)
        audit.append({
            "name": name,
            "args": args,
            "ok": ok,
            "error": err,
        })
        payload = json.dumps(result, ensure_ascii=False, default=str)
        if len(payload) > MAX_TOOL_RESULT_CHARS:
            payload = payload[:MAX_TOOL_RESULT_CHARS] + "…"
        blocks.append(f"[{name}] {payload}")
    text = "\n".join(blocks) if blocks else ""
    return audit, text
