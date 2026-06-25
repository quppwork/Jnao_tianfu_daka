"""豆包 Ark 对话客户端 — 全平台 AI 统一入口"""

from collections.abc import AsyncIterator

import httpx
from config.loader import load_settings
from app.core.logger import get_logger

logger = get_logger("doubao")

DEFAULT_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"


def _sanitize_api_base(value: str | None) -> str:
    base = (value or "").strip()
    if not base or base.startswith("${") or not base.startswith("http"):
        return DEFAULT_API_BASE
    return base.rstrip("/")


def is_configured() -> bool:
    cfg = load_settings().get("doubao", {})
    key = str(cfg.get("api_key", "") or "").strip()
    if not key or key.startswith("${") or key.startswith("your-"):
        return False
    base = _sanitize_api_base(cfg.get("api_base"))
    return bool(key and base.startswith("http"))


def _cfg() -> dict:
    settings = load_settings()
    cfg = settings.get("doubao", {})
    key = str(cfg.get("api_key", "") or "").strip()
    if key.startswith("${"):
        key = ""
    return {
        "api_key": key,
        "api_base": _sanitize_api_base(cfg.get("api_base")),
        "model": cfg.get("model", "doubao-seed-1-6-250615"),
        "vision_model": cfg.get("vision_model") or cfg.get("model", "doubao-seed-1-6-250615"),
    }


def _build_messages(
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
) -> list[dict]:
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for item in history[-10:]:
            role = item.get("role", "user")
            if role == "assistant":
                role = "assistant"
            elif role in ("ai", "bot"):
                role = "assistant"
            else:
                role = "user"
            content = item.get("content") or item.get("text") or ""
            if content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    return messages


async def chat_completion(
    *,
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
    max_tokens: int = 500,
    timeout: float = 30,
) -> str | None:
    cfg = _cfg()
    if not cfg["api_key"]:
        return None

    messages = _build_messages(system_prompt, user_message, history)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{cfg['api_base']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {cfg['api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": cfg["model"],
                    "messages": messages,
                    "max_tokens": max_tokens,
                },
            )
        if resp.status_code != 200:
            logger.error(f"Doubao error {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except httpx.HTTPError as e:
        logger.warning(f"Doubao request failed: {e}")
        return None
    except (KeyError, IndexError, ValueError) as e:
        logger.warning(f"Doubao response parse failed: {e}")
        return None


async def vision_chat_completion(
    *,
    system_prompt: str,
    user_message: str,
    image_data_url: str,
    history: list[dict] | None = None,
    max_tokens: int = 800,
    timeout: float = 60,
) -> str | None:
    """多模态识题 + 解答（OpenAI 兼容 image_url 格式）"""
    cfg = _cfg()
    if not cfg["api_key"]:
        return None

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for item in history[-8:]:
            role = "assistant" if item.get("role") in ("assistant", "ai", "bot") else "user"
            content = item.get("content") or item.get("text") or ""
            if content:
                messages.append({"role": role, "content": content})
    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_message},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        }
    )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{cfg['api_base']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {cfg['api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": cfg["vision_model"],
                    "messages": messages,
                    "max_tokens": max_tokens,
                },
            )
        if resp.status_code != 200:
            logger.error(f"Doubao vision error {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except httpx.HTTPError as e:
        logger.warning(f"Doubao vision request failed: {e}")
        return None
    except (KeyError, IndexError, ValueError) as e:
        logger.warning(f"Doubao vision parse failed: {e}")
        return None


async def chat_completion_stream(
    *,
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
    max_tokens: int = 500,
) -> AsyncIterator[str]:
    """流式输出：优先真流式，失败则整段回退"""
    cfg = _cfg()
    if not cfg["api_key"]:
        yield "[ERROR] 豆包 API 未配置"
        return

    messages = _build_messages(system_prompt, user_message, history)
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{cfg['api_base']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {cfg['api_key']}",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    logger.error(f"Doubao stream error {resp.status_code}: {body[:200]}")
                    yield "[ERROR] 豆包服务异常"
                    return
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    chunk = line[6:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        import json

                        data = json.loads(chunk)
                        delta = data["choices"][0].get("delta", {})
                        text = delta.get("content", "")
                        if text:
                            yield text
                    except Exception:
                        continue
    except Exception as e:
        logger.error(f"Doubao stream failed: {e}")
        full = await chat_completion(
            system_prompt=system_prompt,
            user_message=user_message,
            history=history,
            max_tokens=max_tokens,
        )
        if full:
            yield full
        else:
            yield f"[ERROR] {e}"
