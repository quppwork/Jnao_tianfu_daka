"""知识源目录 — 供 Agent 感知可调用的百炼问答服务。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.logger import get_logger

logger = get_logger("kb.registry")

# 放在 config/：生产 compose 把 named volume 挂到 /app/data，会盖住镜像里的 data/，
# 导致 registry 空 → guide_kb_agent_ready=False → 退化成 retrieve+豆包（答案变短）。
_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY_PATH = _ROOT / "config" / "kb_registry.yaml"
_LEGACY_REGISTRY_PATH = _ROOT / "data" / "kb_registry.yaml"

# env 可覆盖 registry 中的 aid（便于生产不改 yaml）
_ENV_AID_KEYS = {
    "video_practice": "BAILIAN_KB_QA_VIDEO_AID",
    "talent_doc": "BAILIAN_KB_QA_DOC_AID",
}
_ENV_INDEX_KEYS = {
    "video_practice": "BAILIAN_VIDEO_INDEX_ID",
    "talent_doc": "BAILIAN_INDEX_ID",
}


@dataclass(frozen=True)
class KnowledgeSource:
    key: str
    name: str
    aid: str
    index_id: str
    tags: tuple[str, ...] = ()
    summary: str = ""

    def to_agent_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "aid": self.aid,
            "index_id": self.index_id,
            "tags": list(self.tags),
            "summary": self.summary,
        }


@dataclass
class KnowledgeRegistry:
    sources: tuple[KnowledgeSource, ...] = field(default_factory=tuple)

    def list_sources(self) -> list[dict[str, Any]]:
        return [s.to_agent_dict() for s in self.sources]

    def get(self, key: str) -> KnowledgeSource | None:
        k = (key or "").strip()
        for s in self.sources:
            if s.key == k:
                return s
        return None

    def get_by_aid(self, aid: str) -> KnowledgeSource | None:
        a = (aid or "").strip()
        for s in self.sources:
            if s.aid == a:
                return s
        return None

    def resolve(self, *, source_key: str | None = None, aid: str | None = None) -> KnowledgeSource | None:
        if source_key:
            found = self.get(source_key)
            if found:
                return found
        if aid:
            return self.get_by_aid(aid)
        return None


def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    key = raw.get("key") or ""
    aid_env = _ENV_AID_KEYS.get(key)
    idx_env = _ENV_INDEX_KEYS.get(key)
    if aid_env:
        v = (os.getenv(aid_env) or "").strip()
        if v:
            raw = {**raw, "aid": v}
    if idx_env:
        v = (os.getenv(idx_env) or "").strip()
        if v:
            raw = {**raw, "index_id": v}
    return raw


def resolve_registry_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    if _REGISTRY_PATH.is_file():
        return _REGISTRY_PATH
    if _LEGACY_REGISTRY_PATH.is_file():
        return _LEGACY_REGISTRY_PATH
    return _REGISTRY_PATH


def load_kb_registry(*, path: Path | None = None) -> KnowledgeRegistry:
    p = resolve_registry_path(path)
    if not p.is_file():
        logger.warning("kb_registry missing: %s (also tried %s)", p, _LEGACY_REGISTRY_PATH)
        return KnowledgeRegistry()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    items: list[KnowledgeSource] = []
    for raw in data.get("sources") or []:
        if not isinstance(raw, dict):
            continue
        raw = _apply_env_overrides(raw)
        key = str(raw.get("key") or "").strip()
        aid = str(raw.get("aid") or "").strip()
        if not key or not aid:
            continue
        tags = raw.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        items.append(
            KnowledgeSource(
                key=key,
                name=str(raw.get("name") or key),
                aid=aid,
                index_id=str(raw.get("index_id") or ""),
                tags=tuple(str(t).strip() for t in tags if str(t).strip()),
                summary=str(raw.get("summary") or "").strip(),
            )
        )
    return KnowledgeRegistry(sources=tuple(items))


@lru_cache(maxsize=1)
def get_kb_registry() -> KnowledgeRegistry:
    return load_kb_registry()
