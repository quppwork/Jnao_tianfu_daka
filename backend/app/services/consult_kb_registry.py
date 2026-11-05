"""咨询知识库注册表 — 大宇 / 五者两套；仅 published 可检索。"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "config" / "consult_kb_registry.yaml"

_DEFAULT_DAYU_FALLBACK = (
    "我现在没有足够的已确认资料回答这个问题。"
    "你可以查看相关帮助页，或点击「联系人工」说明具体情况。"
)
_DEFAULT_TALENT_FALLBACK = (
    "仅凭这段描述，我不能判断孩子的天赋类型。"
    "你可以先查看本人的测评报告；需要结合个人情况解读时，请联系老师。"
)


def _agent_key(persona: str | None) -> str:
    code = (persona or "dayu").strip().lower()
    return "dayu" if code == "dayu" else "talent"


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    if not _REGISTRY_PATH.is_file():
        return {"version": "missing", "agents": {}}
    with open(_REGISTRY_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {"version": "invalid", "agents": {}}


def clear_registry_cache() -> None:
    load_registry.cache_clear()


def _doc_effective(doc: dict[str, Any], *, today: date | None = None) -> bool:
    if str(doc.get("status") or "").lower() != "published":
        return False
    today = today or date.today()
    start = doc.get("effective_from")
    end = doc.get("effective_to")
    if start:
        try:
            if today < date.fromisoformat(str(start)[:10]):
                return False
        except ValueError:
            pass
    if end:
        try:
            if today > date.fromisoformat(str(end)[:10]):
                return False
        except ValueError:
            pass
    return True


def published_docs_for(persona: str | None) -> list[str]:
    reg = load_registry()
    agents = reg.get("agents") or {}
    block = agents.get(_agent_key(persona)) or {}
    names: list[str] = []
    for doc in block.get("docs") or []:
        if isinstance(doc, dict) and _doc_effective(doc):
            name = str(doc.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def fallback_for(persona: str | None) -> str:
    reg = load_registry()
    agents = reg.get("agents") or {}
    block = agents.get(_agent_key(persona)) or {}
    text = str(block.get("fallback") or "").strip()
    if text:
        return text
    return _DEFAULT_DAYU_FALLBACK if _agent_key(persona) == "dayu" else _DEFAULT_TALENT_FALLBACK


def registry_public_summary() -> dict[str, Any]:
    reg = load_registry()
    out_agents: dict[str, Any] = {}
    for key in ("dayu", "talent"):
        block = (reg.get("agents") or {}).get(key) or {}
        docs = [
            {
                "name": d.get("name"),
                "status": d.get("status"),
                "version": d.get("version"),
                "owner": d.get("owner"),
                "reviewed_by": d.get("reviewed_by"),
                "effective": _doc_effective(d) if isinstance(d, dict) else False,
            }
            for d in (block.get("docs") or [])
            if isinstance(d, dict)
        ]
        out_agents[key] = {
            "title": block.get("title"),
            "fallback": block.get("fallback"),
            "published_docs": published_docs_for(key),
            "docs": docs,
        }
    return {"version": reg.get("version"), "agents": out_agents}
