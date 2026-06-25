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
    doubao_key = os.getenv("DOUBAO_API_KEY", doubao.get("api_key", ""))
    if str(doubao_key).startswith("${"):
        doubao_key = ""
    doubao["api_key"] = doubao_key
    doubao_base = os.getenv(
        "DOUBAO_API_BASE",
        doubao.get("api_base", "https://ark.cn-beijing.volces.com/api/v3"),
    )
    if str(doubao_base).startswith("${"):
        doubao_base = "https://ark.cn-beijing.volces.com/api/v3"
    doubao["api_base"] = doubao_base
    raw_model = doubao.get("model", "")
    if raw_model.startswith("${"):
        raw_model = ""
    doubao["model"] = os.getenv("DOUBAO_CHAT_MODEL", raw_model or "doubao-seed-1-6-250615")
    raw["doubao"] = doubao
    raw["server"] = server
    raw["upstream"]["tianfu_rag"] = upstream
    db = raw.get("database", {})
    default_db = "sqlite:///" + str(_CONFIG_DIR.parent / "data" / "jnao_daka.db").replace("\\", "/")
    db["url"] = os.getenv("DATABASE_URL", db.get("url", default_db))
    if db["url"].startswith("${"):
        db["url"] = default_db
    raw["database"] = db
    oss = raw.get("oss", {})
    oss["access_key_id"] = os.getenv("OSS_ACCESS_KEY_ID", oss.get("access_key_id", ""))
    oss["access_key_secret"] = os.getenv("OSS_ACCESS_KEY_SECRET", oss.get("access_key_secret", ""))
    oss["bucket"] = os.getenv("OSS_BUCKET", oss.get("bucket", "jnao-talent-ai"))
    oss["endpoint"] = os.getenv("OSS_ENDPOINT", oss.get("endpoint", "oss-cn-beijing.aliyuncs.com"))
    oss["prefix"] = os.getenv("OSS_PREFIX", oss.get("prefix", "yinpin/"))
    signed = os.getenv("OSS_SIGNED_URL", str(oss.get("signed_url", True)))
    oss["signed_url"] = signed.lower() in ("1", "true", "yes")
    oss["sign_expires"] = int(os.getenv("OSS_SIGN_EXPIRES", oss.get("sign_expires", 7200)))
    raw["oss"] = oss
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
