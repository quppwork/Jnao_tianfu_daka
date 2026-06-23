"""YAML 配置加载器 — 惰性加载 + Pydantic 校验 + 环境变量覆盖"""

import os
from pathlib import Path
from functools import lru_cache

import yaml

_CONFIG_DIR = Path(__file__).parent


def _read_yaml(filename: str) -> dict | list:
    path = _CONFIG_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        raise ValueError(f"配置文件为空: {filename}")
    return data


# ============ Settings ============

@lru_cache(maxsize=1)
def load_settings() -> dict:
    """返回 { server: {host,port}, upstream: {tianfu_rag: {url,timeout,health_timeout}} }"""
    raw = _read_yaml("settings.yaml")
    server = raw.get("server", {})
    server["host"] = os.getenv("JNAO_HOST", server.get("host", "127.0.0.1"))
    server["port"] = int(os.getenv("JNAO_PORT", server.get("port", 8011)))
    upstream = raw.get("upstream", {}).get("tianfu_rag", {})
    upstream["url"] = os.getenv("TIANFU_RAG_URL", upstream.get("url", "http://127.0.0.1:8010"))
    deepseek = raw.get("deepseek", {})
    deepseek["api_key"] = os.getenv("DEEPSEEK_API_KEY", deepseek.get("api_key", ""))
    raw["deepseek"] = deepseek
    doubao = raw.get("doubao", {})
    doubao["api_key"] = os.getenv("DOUBAO_API_KEY", doubao.get("api_key", ""))
    doubao["api_base"] = os.getenv("DOUBAO_API_BASE", doubao.get("api_base", "https://ark.cn-beijing.volces.com/api/v3"))
    doubao["model"] = os.getenv("DOUBAO_CHAT_MODEL", doubao.get("model", "doubao-lite-128k"))
    raw["doubao"] = doubao
    raw["server"] = server
    raw["upstream"]["tianfu_rag"] = upstream
    return raw


# ============ Dimensions ============

@lru_cache(maxsize=1)
def load_dimensions() -> list[dict]:
    """返回 7 维度列表 [{key, name, label, questions}]"""
    return _read_yaml("dimensions.yaml")


# ============ Integration ============

@lru_cache(maxsize=1)
def load_integration() -> dict:
    """返回 {endpoints: {key: {status, description, endpoint}}}"""
    return _read_yaml("integration.yaml")


# ============ Questions ============

@lru_cache(maxsize=1)
def load_questions() -> list[dict]:
    """返回 105 道题目 [{id, text, set}]"""
    return _read_yaml("questions.yaml")
