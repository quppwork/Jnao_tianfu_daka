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
    deepseek = raw.get("deepseek", {}) or {}
    ds_key = os.getenv("DEEPSEEK_API_KEY", deepseek.get("api_key", ""))
    if str(ds_key).startswith("${"):
        ds_key = ""
    deepseek["api_key"] = ds_key
    ds_base = os.getenv(
        "DEEPSEEK_API_BASE",
        deepseek.get("api_base", "https://api.deepseek.com"),
    )
    if str(ds_base).startswith("${") or not str(ds_base).startswith("http"):
        ds_base = "https://api.deepseek.com"
    deepseek["api_base"] = str(ds_base).rstrip("/")
    ds_model = os.getenv("DEEPSEEK_CHAT_MODEL", deepseek.get("model", "deepseek-v4-pro"))
    if str(ds_model).startswith("${") or not str(ds_model).strip():
        ds_model = "deepseek-v4-pro"
    deepseek["model"] = str(ds_model).strip()
    ds_vision = os.getenv(
        "DEEPSEEK_VISION_MODEL",
        deepseek.get("vision_model") or "deepseek-flash",
    )
    if str(ds_vision).startswith("${") or not str(ds_vision).strip():
        ds_vision = "deepseek-flash"
    deepseek["vision_model"] = str(ds_vision).strip()
    raw["deepseek"] = deepseek
    # 豆包停用：不再从环境注入；旧 DOUBAO_* 忽略
    raw["doubao"] = {"api_key": "", "api_base": "", "model": "", "vision_model": ""}
    raw["server"] = server
    raw["upstream"]["tianfu_rag"] = upstream
    db = raw.get("database", {})
    default_db = "sqlite:///" + str(_CONFIG_DIR.parent / "data" / "jnao_daka.db").replace("\\", "/")
    db["url"] = os.getenv("DATABASE_URL", db.get("url", default_db))
    if db["url"].startswith("${"):
        db["url"] = default_db
    raw["database"] = db
    oss = raw.get("oss", {})
    oss_id = os.getenv("OSS_ACCESS_KEY_ID", oss.get("access_key_id", ""))
    oss_secret = os.getenv("OSS_ACCESS_KEY_SECRET", oss.get("access_key_secret", ""))
    if str(oss_id).startswith("${"):
        oss_id = ""
    if str(oss_secret).startswith("${"):
        oss_secret = ""
    oss["access_key_id"] = oss_id
    oss["access_key_secret"] = oss_secret
    oss["bucket"] = os.getenv("OSS_BUCKET", oss.get("bucket", "jnao-talent-ai"))
    oss["endpoint"] = os.getenv("OSS_ENDPOINT", oss.get("endpoint", "oss-cn-beijing.aliyuncs.com"))
    oss_prefix = os.getenv("OSS_PREFIX", oss.get("prefix", "yinpin/"))
    oss["prefix"] = oss_prefix.split(",")[0].strip()
    oss["prefixes"] = [p.strip() for p in oss_prefix.split(",") if p.strip()]
    signed = os.getenv("OSS_SIGNED_URL", str(oss.get("signed_url", True)))
    oss["signed_url"] = signed.lower() in ("1", "true", "yes")
    oss["sign_expires"] = int(os.getenv("OSS_SIGN_EXPIRES", oss.get("sign_expires", 7200)))
    oss["cdn_domain"] = os.getenv("OSS_CDN_DOMAIN", oss.get("cdn_domain", "")).strip()
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


# ============ Training curriculum (推课业务规则 v2.0) ============

@lru_cache(maxsize=1)
def load_training_curriculum() -> dict:
    """返回 training_curriculum.yaml — 时长公式 / 技能分类 / 选修规则"""
    path = _CONFIG_DIR / "training_curriculum.yaml"
    if not path.exists():
        return {}
    data = _read_yaml("training_curriculum.yaml")
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def load_training_tier_thresholds() -> dict:
    """🆕 v2.0 返回 training_tier_thresholds.yaml — 技能 Tier×学段→达标阈值"""
    path = _CONFIG_DIR / "training_tier_thresholds.yaml"
    if not path.exists():
        return {}
    data = _read_yaml("training_tier_thresholds.yaml")
    return data if isinstance(data, dict) else {}


# ============ Legacy (v1.0 兼容，后续废弃) ============

@lru_cache(maxsize=1)
def load_training_advance_rules() -> dict:
    """@deprecated v2.0: 使用 load_training_tier_thresholds() 替代"""
    path = _CONFIG_DIR / "training_advance_rules.yaml"
    if not path.exists():
        return {}
    data = _read_yaml("training_advance_rules.yaml")
    return data if isinstance(data, dict) else {}


# ============ Questions ============

@lru_cache(maxsize=1)
def load_questions() -> list[dict]:
    """返回 105 道题目 [{id, text, set}]"""
    return _read_yaml("questions.yaml")
