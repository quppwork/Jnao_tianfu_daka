"""工具目录 + 调度：原生 function-calling 优先，启发式 / JSON 兜底。"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.agents.guide.tools import call_tool, list_tools
from app.core.logger import get_logger

logger = get_logger("guide.tools")

# 单轮规划最多工具数；多轮累计上限见 runner
MAX_TOOLS_PER_TURN = 2
MAX_TOOL_RESULT_CHARS = 1800
# 多步 tool loop：规划轮次（含首轮）
MAX_TOOL_ROUNDS = 3
# 整轮对话累计工具调用上限
MAX_TOOLS_TOTAL = 4

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
            "方案怎么排",
            "怎么排的",
            "训练方案",
            "可以训练",
            "能练什么",
            "下一等级",
            "下一级",
            "怎么晋级",
            "如何晋级",
        ),
    ),
    "get_checkin_timeline": (
        "近期打卡时间线摘要",
        ("打卡", "上周", "最近几天", "练了几次", "多久没", "历史", "时间线"),
    ),
    "get_day_checkin_detail": (
        "某一训练日的打卡内容摘要（技能/用时/字数/结果/备注等，不含课件文件）",
        (
            "打卡内容",
            "打卡详情",
            "打卡了什么",
            "练了什么",
            "填了什么",
            "用时多少",
            "多少字",
            "备注写了",
            "今天打了",
            "昨日打卡",
            "那天练",
            "最近一次",
            "上次打卡",
            "上一次打卡",
            "最近一笔",
            "打卡数值",
            "具体数值",
            "历史记录",
        ),
    ),
    "get_skill_progress": (
        "分技能档位快照（仅供参考；禁止用其解释晋级条件/达标次数）",
        ("进度", "tier", "Tier", "技能", "哪项弱", "哪项强", "等级", "档位"),
    ),
    "suggest_next_action": (
        "建议下一步入口（talent/train/qa/growth）",
        ("接下来", "下一步", "该做什么", "建议去", "做什么好"),
    ),
    "get_training_courses": (
        "平台可训练能力目录（必修/选修名称，只读）",
        ("有哪些课", "训练能力", "能练什么", "课程列表", "必修选修"),
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
    "get_day_checkin_detail": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": (
                    "训练日 YYYY-MM-DD；today/今日=当天；"
                    "latest/最近一次=最近有打卡的一天；省略则今日，今日无记录则回退最近一次"
                ),
            },
        },
        "additionalProperties": False,
    },
}

FC_PLANNER_SYSTEM = (
    "你是首页引导的工具调度器。根据用户问题决定是否调用只读工具。"
    "需要查画像、天赋报告摘要、今日训练、某日打卡内容、打卡时间线、技能进度或下一步建议时再调用；"
    "问「打卡了什么/用时/字数/备注」等明细时用 get_day_checkin_detail；"
    "问晋级/下一等级/方案怎么排时优先 get_today_plan（可附 get_skill_progress），结果仅作摘要，勿当规则说明书；"
    "若近几轮对话已谈今日训练、本轮又问天赋（或反过来），优先同时取 get_talent_report_summary 与 get_today_plan。"
    "最多调用 2 个工具；双工具仅限合理组合（如天赋+今日、今日+打卡明细、今日+进度）。"
    "纯闲聊不必调用。不要编造工具结果。"
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
            args: dict[str, Any] = {}
            if name == "get_checkin_timeline":
                args["limit"] = 14
            if name == "get_day_checkin_detail" and any(
                k in (message or "")
                for k in (
                    "最近一次",
                    "上次打卡",
                    "上一次",
                    "最近一笔",
                    "历史记录",
                    "打卡数值",
                    "具体数值",
                )
            ):
                args["date"] = "latest"
            picks.append(_normalize_pick(name, args))
        if len(picks) >= MAX_TOOLS_PER_TURN:
            break
    return picks


_TRAIN_HISTORY_KEYS = (
    "今日训练",
    "今天练",
    "训练如何",
    "打卡",
    "练了",
    "完成",
    "训练",
)
_TALENT_HISTORY_KEYS = (
    "天赋",
    "测评",
    "报告",
    "赢者",
    "学者",
    "思者",
    "德者",
    "行者",
    "潜能",
)

# 交叉补工具只看近几轮，避免旧闲聊误触发
CROSS_HISTORY_TURNS = 4

# 双工具白名单（无序对）；单工具始终允许
ALLOWED_TOOL_PAIRS: frozenset[frozenset[str]] = frozenset({
    frozenset({"get_talent_report_summary", "get_today_plan"}),
    frozenset({"get_today_plan", "get_skill_progress"}),
    frozenset({"get_today_plan", "get_checkin_timeline"}),
    frozenset({"get_today_plan", "get_day_checkin_detail"}),
    frozenset({"get_day_checkin_detail", "get_talent_report_summary"}),
    frozenset({"get_day_checkin_detail", "get_checkin_timeline"}),
    frozenset({"get_profile", "get_talent_report_summary"}),
    frozenset({"get_profile", "get_today_plan"}),
})


def _history_blob(
    history: list[dict] | None,
    *,
    max_turns: int = CROSS_HISTORY_TURNS,
) -> str:
    if not history:
        return ""
    parts: list[str] = []
    for item in history[-max_turns:]:
        content = item.get("content") or item.get("text") or ""
        if content:
            parts.append(str(content))
    return "\n".join(parts)


def clamp_to_allowed_pairs(picks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """超过 1 个工具时，仅保留白名单内的组合；否则只留主工具（第一个）。"""
    if len(picks) <= 1:
        return picks
    trimmed = picks[:MAX_TOOLS_PER_TURN]
    names = frozenset(p["name"] for p in trimmed)
    if names in ALLOWED_TOOL_PAIRS:
        return trimmed
    return trimmed[:1]


def enrich_picks_cross_topic(
    message: str,
    picks: list[dict[str, Any]],
    *,
    history: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """多轮关联：问天赋且近史谈过训练 → 补今日摘要；问训练且近史谈过天赋 → 补天赋摘要。"""
    if not picks:
        return picks
    names = {p["name"] for p in picks}
    hist = _history_blob(history, max_turns=CROSS_HISTORY_TURNS)
    msg = (message or "").strip()
    out = list(picks)

    def _add(name: str) -> None:
        if name in names or len(out) >= MAX_TOOLS_PER_TURN:
            return
        trial = frozenset(names | {name})
        if len(trial) == 2 and trial not in ALLOWED_TOOL_PAIRS:
            return
        out.append(_normalize_pick(name, {}))
        names.add(name)

    talent_now = "get_talent_report_summary" in names or any(
        k in msg for k in TOOL_SPECS["get_talent_report_summary"][1]
    )
    train_now = "get_today_plan" in names or any(
        k in msg for k in TOOL_SPECS["get_today_plan"][1]
    )
    train_before = any(k in hist for k in _TRAIN_HISTORY_KEYS)
    talent_before = any(k in hist for k in _TALENT_HISTORY_KEYS)

    if talent_now and train_before:
        _add("get_today_plan")
    if train_now and talent_before:
        _add("get_talent_report_summary")
    if talent_now and train_now:
        _add("get_today_plan")
        _add("get_talent_report_summary")
    return clamp_to_allowed_pairs(out)


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
    """调度：归一 → FC → 启发式；业务问句且仍空时可 JSON 二次规划；交叉补齐。"""
    from app.agents.guide.tools.query_normalize import (
        looks_like_business_query,
        normalize_guide_query,
    )

    raw = (message or "").strip()
    norm = normalize_guide_query(raw)
    plan_msg = norm or raw

    fc_attempted = False
    picks: list[dict[str, Any]] = []
    if prefer_native_fc:
        picks = await plan_tools_native_fc(plan_msg, history=history)
        fc_attempted = True
        if picks:
            return enrich_picks_cross_topic(plan_msg, picks, history=history)
    picks = plan_tools_heuristic(plan_msg)
    if picks:
        return enrich_picks_cross_topic(plan_msg, picks, history=history)
    # R4：FC 已试仍空，且像业务问句 → 允许 JSON 二次规划（原先仅未走 FC 才兜底）
    if use_llm_fallback and (
        not fc_attempted or looks_like_business_query(plan_msg)
    ):
        picks = await plan_tools_llm(plan_msg)
        if picks:
            return enrich_picks_cross_topic(plan_msg, picks, history=history)
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
        entry: dict[str, Any] = {
            "name": name,
            "args": args,
            "ok": ok,
            "error": err,
            "source": pick.get("source"),
        }
        if (
            ok
            and name == "get_day_checkin_detail"
            and isinstance(result, dict)
        ):
            qd = str(result.get("query_date") or "").strip()[:10]
            if len(qd) == 10:
                entry["query_date"] = qd
            entry["record_count"] = int(result.get("record_count") or 0)
            entry["mode"] = result.get("mode")
        if ok:
            from app.agents.guide.ui_blocks import result_brief_for_tool

            brief = result_brief_for_tool(name, result)
            if brief:
                entry["result_brief"] = brief
        audit.append(entry)
        payload = json.dumps(result, ensure_ascii=False, default=str)
        if len(payload) > MAX_TOOL_RESULT_CHARS:
            payload = payload[:MAX_TOOL_RESULT_CHARS] + "…"
        blocks.append(f"[{name}] {payload}")
    text = "\n".join(blocks) if blocks else ""
    return audit, text


def pick_key(pick: dict[str, Any]) -> str:
    """工具去重键：name + 稳定序列化 args。"""
    name = str(pick.get("name") or "")
    args = pick.get("args") if isinstance(pick.get("args"), dict) else {}
    return f"{name}:{json.dumps(args, ensure_ascii=False, sort_keys=True, default=str)}"


def _used_names(audit: list[dict[str, Any]]) -> set[str]:
    return {str(a.get("name") or "") for a in audit if a.get("name")}


def _used_keys(audit: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for a in audit:
        out.add(pick_key({"name": a.get("name"), "args": a.get("args") or {}}))
    return out


def suggest_followup_picks(
    message: str,
    *,
    used_audit: list[dict[str, Any]],
    history: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """根据首轮（及已有）工具结果决定是否补查；纯规则、可测、无 LLM。

    典型：问晋级但只查了今日方案 → 补档位；今日打卡为空 → 补 latest。
    """
    _ = history
    text = (message or "").strip()
    if not text or not used_audit:
        return []

    names = _used_names(used_audit)
    keys = _used_keys(used_audit)
    candidates: list[dict[str, Any]] = []

    def _offer(name: str, args: dict[str, Any] | None = None) -> None:
        pick = _normalize_pick(name, args or {})
        pick["source"] = "followup"
        k = pick_key(pick)
        if k in keys:
            return
        # 与已有工具组成的集合须为单工具或白名单对
        trial_names = frozenset(names | {name})
        if len(trial_names) > 2:
            return
        if len(trial_names) == 2 and trial_names not in ALLOWED_TOOL_PAIRS:
            # 允许「仅补查同名工具不同 args」（如 day_checkin latest）
            if name not in names:
                return
        candidates.append(pick)
        keys.add(k)
        names.add(name)

    # 1) 今日/指定日打卡为空 → 再查最近一次
    for a in used_audit:
        if a.get("name") != "get_day_checkin_detail" or not a.get("ok"):
            continue
        if int(a.get("record_count") or 0) > 0:
            continue
        mode = a.get("mode")
        if mode in ("today", "date", None) and mode != "latest":
            args0 = a.get("args") if isinstance(a.get("args"), dict) else {}
            if str(args0.get("date") or "").lower() not in (
                "latest", "last", "最近", "最近一次", "上次", "最近一笔", "上一次",
            ):
                _offer("get_day_checkin_detail", {"date": "latest"})

    # 2) 问等级/晋级/进度 → 需要档位快照
    level_keys = (
        "下一等级", "下一级", "怎么晋级", "如何晋级", "晋级", "等级", "档位", "进度",
    )
    if any(k in text for k in level_keys):
        _offer("get_skill_progress")
        _offer("get_today_plan")

    # 3) 问方案/能练什么 → 今日摘要（课程目录首轮常已命中，此处补今日）
    plan_keys = (
        "方案怎么排", "怎么排的", "训练方案", "能练什么", "可以训练", "练什么",
        "今日安排", "今天安排",
    )
    if any(k in text for k in plan_keys):
        _offer("get_today_plan")

    # 4) 问打卡数值/内容且尚未查明细
    detail_keys = (
        "打卡内容", "打卡详情", "打卡数值", "具体数值", "最近一次", "上次打卡",
    )
    if any(k in text for k in detail_keys) and "get_day_checkin_detail" not in _used_names(used_audit):
        if any(k in text for k in ("最近一次", "上次", "上一次", "最近一笔")):
            _offer("get_day_checkin_detail", {"date": "latest"})
        else:
            _offer("get_day_checkin_detail", {})

    # 钳制：本轮最多补 MAX_TOOLS_PER_TURN 个，且累计名集合合法
    out: list[dict[str, Any]] = []
    acc_names = set(_used_names(used_audit))
    for pick in candidates:
        if len(out) >= MAX_TOOLS_PER_TURN:
            break
        n = pick["name"]
        trial = frozenset(acc_names | {n})
        if len(trial) > 2:
            # 已有 2 个不同名时，只允许同名不同 args（已在 _offer 处理）
            if n not in acc_names:
                continue
        elif len(trial) == 2 and trial not in ALLOWED_TOOL_PAIRS and n not in acc_names:
            continue
        out.append(pick)
        acc_names.add(n)
    return out


def build_grounding_hint(
    message: str,
    *,
    tools_used: list[dict[str, Any]],
    tool_block: str,
) -> str:
    """R3：注入系统侧 grounding / 澄清提示（追加在工具块后）。"""
    from app.agents.guide.tools.query_normalize import (
        looks_like_business_query,
        looks_like_needs_clarify,
    )

    lines: list[str] = []
    if looks_like_needs_clarify(message):
        lines.append(
            "【澄清】用户问题缺关键信息（如哪一天/哪项技能）。"
            "先用一句问清缺的槽位，再给建议；不要编造日期或数值。"
        )
    if not tools_used and looks_like_business_query(message):
        lines.append(
            "【调度】本轮未查到工具数据。"
            "若用户在问进度/打卡/方案等具体事实，先澄清或引导去对应页面查看，禁止编造数字。"
        )
    if tools_used and tool_block:
        empty_detail = any(
            t.get("name") == "get_day_checkin_detail"
            and t.get("ok")
            and int(t.get("record_count") or 0) == 0
            for t in tools_used
        )
        if empty_detail:
            lines.append(
                "【澄清】打卡明细查询结果为空。"
                "如实说明没有记录或已回退最近一次的日期；不要说「有记录」却编造内容。"
            )
        else:
            lines.append(
                "【Grounding】回复中的日期、用时、字数、技能名、备注必须来自上方工具 JSON；"
                "工具没有的字段不要编造。"
            )
    return "\n".join(lines)
