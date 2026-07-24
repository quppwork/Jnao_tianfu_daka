"""工具目录 + 调度：原生 function-calling 优先，启发式 / JSON 兜底。"""

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
        "画像与天赋标签（昵称/年级/是否测评）",
        ("画像", "年级", "我是谁"),
    ),
    "get_talent_report_summary": (
        "有效天赋报告摘要（解读/建议，非整包报告）",
        (
            "天赋",
            "测评",
            "报告",
            "什么者",
            "潜能",
            "赢者",
            "学者",
            "思者",
            "德者",
            "行者",
            "我这个天赋",
            "天赋如何",
            "解读",
        ),
    ),
    "get_today_plan": (
        "今日训练摘要（有无方案/是否开始/完成几项/计划时长；不含排课明细）",
        (
            "今天练",
            "今日训练",
            "练了吗",
            "完成几项",
            "今天的方案",
            "今日方案",
            "练什么",
            "训练项目",
            "推荐",
            "练多久",
            "训练多久",
            "多久合适",
            "多少分钟",
            "今日安排",
            "今天安排",
        ),
    ),
    "get_checkin_timeline": (
        "近期打卡时间线摘要",
        ("打卡", "上周", "最近几天", "练了几次", "多久没", "历史", "时间线"),
    ),
    "get_skill_progress": (
        "分技能 Tier 进度快照（勿用于解释晋级规则）",
        ("进度", "tier", "Tier", "技能", "哪项弱", "哪项强", "等级"),
    ),
    "suggest_next_action": (
        "建议下一步入口（talent/train/qa/growth）",
        ("接下来", "下一步", "该做什么", "建议去", "做什么好"),
    ),
}

_TOOL_PARAM_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_checkin_timeline": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "回溯天数，默认 14，最大 30",
                "minimum": 1,
                "maximum": 30,
            },
        },
        "additionalProperties": False,
    },
}

FC_PLANNER_SYSTEM = (
    "你是首页引导的工具调度器。根据用户问题决定是否调用只读工具。"
    "需要查画像、天赋报告摘要、今日训练、打卡时间线、技能进度或下一步建议时再调用；"
    "纯闲聊不必调用。最多调用 2 个工具。不要编造工具结果。"
)

PLANNER_SYSTEM = (
    "你是首页引导的工具调度器。根据用户问题决定是否调用只读工具。\n"
    "只输出一行 JSON，不要解释，格式：\n"
    '{"tools":[{"name":"工具名","args":{}}]}\n'
    '不需要工具时：{"tools":[]}\n'
    "最多选 2 个。工具只提供摘要事实，不含排课/晋级算法。可用工具：\n"
    + "\n".join(f"- {n}: {desc}" for n, (desc, _) in TOOL_SPECS.items())
)


def openai_tool_schemas() -> list[dict[str, Any]]:
    """Ark / OpenAI 兼容 tools 列表。"""
    out: list[dict[str, Any]] = []
    for name, (desc, _keys) in TOOL_SPECS.items():
        params = _TOOL_PARAM_SCHEMAS.get(
            name,
            {"type": "object", "properties": {}, "additionalProperties": False},
        )
        out.append({
            "type": "function",
            "function": {
                "name": name,
                "description": desc,
                "parameters": params,
            },
        })
    return out


def _normalize_pick(name: str, args: dict[str, Any] | None) -> dict[str, Any]:
    a = dict(args or {})
    if name == "get_checkin_timeline" and "limit" not in a:
        a["limit"] = 14
    return {"name": name, "args": a}


def parse_native_tool_calls(message: dict | None) -> list[dict[str, Any]]:
    """从 assistant message.tool_calls 解析为 picks。"""
    if not isinstance(message, dict):
        return []
    raw_calls = message.get("tool_calls")
    if not isinstance(raw_calls, list):
        fc = message.get("function_call")
        if isinstance(fc, dict) and fc.get("name"):
            raw_calls = [{"type": "function", "function": fc}]
        else:
            return []
    allowed = set(TOOL_SPECS)
    out: list[dict[str, Any]] = []
    for call in raw_calls:
        if not isinstance(call, dict):
            continue
        fn = call.get("function") if isinstance(call.get("function"), dict) else call
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        if name not in allowed:
            continue
        args_raw = fn.get("arguments", {})
        args: dict[str, Any] = {}
        if isinstance(args_raw, dict):
            args = args_raw
        elif isinstance(args_raw, str) and args_raw.strip():
            try:
                parsed = json.loads(args_raw)
                if isinstance(parsed, dict):
                    args = parsed
            except json.JSONDecodeError:
                args = {}
        out.append(_normalize_pick(str(name), args))
        if len(out) >= MAX_TOOLS_PER_TURN:
            break
    return out


def plan_tools_heuristic(message: str) -> list[dict[str, Any]]:
    """关键词启发式选工具；稳定、可测、零 LLM 成本。"""
    text = (message or "").strip().lower()
    if not text:
        return []
    picks: list[dict[str, Any]] = []
    for name, (_desc, keys) in TOOL_SPECS.items():
        if any(k.lower() in text for k in keys):
            picks.append(_normalize_pick(name, {}))
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
        out.append(_normalize_pick(str(name), args))
        if len(out) >= MAX_TOOLS_PER_TURN:
            break
    return out


async def plan_tools_llm(message: str) -> list[dict[str, Any]]:
    """LLM JSON 调度（未走原生 FC 时的兼容兜底）；失败返回 []。"""
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


async def plan_tools_native_fc(
    message: str,
    *,
    history: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """豆包原生 tools / function-calling 选工具。"""
    from app.services.doubao_client import chat_completion_message, is_configured

    if not is_configured():
        return []
    text = (message or "").strip()
    if not text:
        return []
    list_tools()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": FC_PLANNER_SYSTEM},
    ]
    if history:
        for item in history[-6:]:
            role = item.get("role", "user")
            if role in ("assistant", "ai", "bot"):
                role = "assistant"
            else:
                role = "user"
            content = item.get("content") or item.get("text") or ""
            if content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": text})
    try:
        msg = await chat_completion_message(
            messages=messages,
            tools=openai_tool_schemas(),
            tool_choice="auto",
            max_tokens=300,
            timeout=12,
        )
    except Exception as e:
        logger.warning(f"native FC planner failed: {e}")
        return []
    picks = parse_native_tool_calls(msg)
    if picks:
        logger.info(f"guide FC picks={[p['name'] for p in picks]}")
    return picks


async def plan_tools(
    message: str,
    *,
    history: list[dict] | None = None,
    use_llm_fallback: bool = True,
    prefer_native_fc: bool = True,
) -> list[dict[str, Any]]:
    """调度顺序：原生 FC → 启发式；未走 FC 时才用 JSON 调度兜底。"""
    fc_attempted = False
    if prefer_native_fc:
        picks = await plan_tools_native_fc(message, history=history)
        fc_attempted = True
        if picks:
            return picks
    picks = plan_tools_heuristic(message)
    if picks:
        return picks
    if use_llm_fallback and not fc_attempted:
        return await plan_tools_llm(message)
    return []


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
            "source": pick.get("source"),
        })
        payload = json.dumps(result, ensure_ascii=False, default=str)
        if len(payload) > MAX_TOOL_RESULT_CHARS:
            payload = payload[:MAX_TOOL_RESULT_CHARS] + "…"
        blocks.append(f"[{name}] {payload}")
    text = "\n".join(blocks) if blocks else ""
    return audit, text
