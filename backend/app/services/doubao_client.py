"""统一对话客户端 — DeepSeek（OpenAI 兼容）。模块名 doubao_client 保留以免全仓改 import。"""

from collections.abc import AsyncIterator

import httpx
from config.loader import load_settings
from app.core.logger import get_logger
from app.services.usage_recorder import record_usage

logger = get_logger("llm")

DEFAULT_API_BASE = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_VISION_MODEL = "deepseek-flash"

_http_client: httpx.AsyncClient | None = None


def _get_client(timeout: float) -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=timeout, trust_env=False)
    return _http_client


def _sanitize_api_base(value: str | None) -> str:
    base = (value or "").strip()
    if not base or base.startswith("${") or not base.startswith("http"):
        return DEFAULT_API_BASE
    return base.rstrip("/")


def is_configured() -> bool:
    cfg = _cfg()
    key = str(cfg.get("api_key", "") or "").strip()
    if not key or key.startswith("${") or key.startswith("your-") or key.startswith("sk-your"):
        return False
    return bool(str(cfg.get("api_base") or "").startswith("http"))


def _cfg() -> dict:
    """只走 DeepSeek；不再回落豆包。"""
    settings = load_settings()
    ds = settings.get("deepseek", {}) or {}
    key = str(ds.get("api_key", "") or "").strip()
    if key.startswith("${"):
        key = ""
    model = str(ds.get("model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    vision = str(ds.get("vision_model") or DEFAULT_VISION_MODEL).strip() or DEFAULT_VISION_MODEL
    return {
        "api_key": key,
        "api_base": _sanitize_api_base(ds.get("api_base")),
        "model": model,
        "vision_model": vision,
        "provider": "deepseek",
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


def _record_doubao(
    *,
    api: str,
    model: str | None,
    usage: dict | None,
    stream: bool = False,
    ok: bool = True,
    feature: str | None = None,
) -> None:
    try:
        record_usage(
            provider="deepseek",
            api=api,
            model=model,
            feature=feature,
            usage=usage if isinstance(usage, dict) else None,
            metric_kind="tokens",
            stream=stream,
            ok=ok,
            call_count=1,
        )
    except Exception as e:
        logger.warning("llm usage record skipped: %s", e)


def _message_text(message: dict) -> str | None:
    content = message.get("content")
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(str(part.get("text") or ""))
        content = "".join(parts)
    text = str(content or "").strip()
    return text or None


async def chat_completion(
    *,
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
    max_tokens: int = 500,
    timeout: float = 30,
    feature: str | None = None,
    disable_thinking: bool = True,
) -> str | None:
    """默认关 thinking：v4-pro 推理会吃满 max_tokens，短回复容易 content 为空。"""
    cfg = _cfg()
    if not cfg["api_key"]:
        return None

    messages = _build_messages(system_prompt, user_message, history)

    try:
        client = _get_client(timeout)
        payload = {
            "model": cfg["model"],
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if disable_thinking:
            payload["thinking"] = {"type": "disabled"}
        resp = await client.post(
            f"{cfg['api_base']}/chat/completions",
            headers={
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        if resp.status_code == 400 and disable_thinking and "thinking" in resp.text:
            payload.pop("thinking", None)
            resp = await client.post(
                f"{cfg['api_base']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {cfg['api_key']}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
        if resp.status_code != 200:
            logger.error(f"LLM error {resp.status_code}: {resp.text[:200]}")
            _record_doubao(api="chat.completions", model=cfg["model"], usage=None, ok=False, feature=feature)
            return None
        data = resp.json()
        _record_doubao(
            api="chat.completions",
            model=cfg["model"],
            usage=data.get("usage"),
            feature=feature,
        )
        return _message_text(data["choices"][0]["message"])
    except httpx.HTTPError as e:
        logger.warning(f"LLM request failed: {e}")
        return None
    except (KeyError, IndexError, ValueError) as e:
        logger.warning(f"LLM response parse failed: {e}")
        return None


async def chat_completion_message(
    *,
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = "auto",
    max_tokens: int = 400,
    timeout: float = 30,
    feature: str | None = None,
) -> dict | None:
    """DeepSeek /chat/completions：返回 assistant message（可含 tool_calls）。

    OpenAI 兼容：tools + tool_choice；用于 Guide 原生 function-calling 选工具。
    """
    cfg = _cfg()
    if not cfg["api_key"]:
        return None
    if not messages:
        return None

    payload: dict = {
        "model": cfg["model"],
        "messages": messages,
        "max_tokens": max_tokens,
        # 工具选库也关 thinking，避免拖慢 Guide Agent
        "thinking": {"type": "disabled"},
    }
    if tools:
        payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice

    try:
        client = _get_client(timeout)
        resp = await client.post(
            f"{cfg['api_base']}/chat/completions",
            headers={
                "Authorization": f"Bearer {cfg['api_key']}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        if resp.status_code == 400 and "thinking" in resp.text:
            payload.pop("thinking", None)
            resp = await client.post(
                f"{cfg['api_base']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {cfg['api_key']}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
        if resp.status_code != 200:
            logger.error(
                f"LLM tools error {resp.status_code}: {resp.text[:300]}"
            )
            _record_doubao(api="chat.completions.tools", model=cfg["model"], usage=None, ok=False, feature=feature)
            return None
        data = resp.json()
        _record_doubao(
            api="chat.completions.tools",
            model=cfg["model"],
            usage=data.get("usage"),
            feature=feature,
        )
        msg = data["choices"][0]["message"]
        return msg if isinstance(msg, dict) else None
    except httpx.HTTPError as e:
        logger.warning(
            "LLM tools request failed: type=%s timeout=%s err=%r",
            type(e).__name__,
            timeout,
            e,
        )
        return None
    except (KeyError, IndexError, TypeError, ValueError) as e:
        logger.warning(f"LLM tools parse failed: {e}")
        return None


async def vision_chat_completion(
    *,
    system_prompt: str,
    user_message: str,
    image_data_url: str,
    history: list[dict] | None = None,
    max_tokens: int = 800,
    timeout: float = 60,
    feature: str | None = None,
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
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
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
            logger.error(f"LLM vision error {resp.status_code}: {resp.text[:200]}")
            _record_doubao(api="chat.completions.vision", model=cfg["vision_model"], usage=None, ok=False, feature=feature)
            return None
        data = resp.json()
        _record_doubao(
            api="chat.completions.vision",
            model=cfg["vision_model"],
            usage=data.get("usage"),
            feature=feature,
        )
        return data["choices"][0]["message"]["content"]
    except httpx.HTTPError as e:
        logger.warning(f"LLM vision request failed: {e}")
        return None
    except (KeyError, IndexError, ValueError) as e:
        logger.warning(f"LLM vision parse failed: {e}")
        return None


async def chat_completion_stream(
    *,
    system_prompt: str,
    user_message: str,
    history: list[dict] | None = None,
    max_tokens: int = 500,
    feature: str | None = None,
) -> AsyncIterator[str]:
    """流式输出：优先真流式，失败则整段回退"""
    cfg = _cfg()
    if not cfg["api_key"]:
        yield "[ERROR] DeepSeek API 未配置"
        return

    messages = _build_messages(system_prompt, user_message, history)
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        "thinking": {"type": "disabled"},
    }
    usage_acc: dict | None = None
    yielded_any = False

    try:
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
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
                    logger.error(f"LLM stream error {resp.status_code}: {body[:200]}")
                    _record_doubao(
                        api="chat.completions.stream",
                        model=cfg["model"],
                        usage=None,
                        stream=True,
                        ok=False,
                        feature=feature,
                    )
                    yield "[ERROR] DeepSeek 服务异常"
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
                        if isinstance(data.get("usage"), dict):
                            usage_acc = data["usage"]
                        choices = data.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {}) or {}
                        text = delta.get("content", "")
                        if text:
                            yielded_any = True
                            yield text
                    except Exception:
                        continue
        if yielded_any or usage_acc:
            _record_doubao(
                api="chat.completions.stream",
                model=cfg["model"],
                usage=usage_acc,
                stream=True,
                feature=feature,
            )
    except Exception as e:
        logger.error(f"LLM stream failed: {e}")
        full = await chat_completion(
            system_prompt=system_prompt,
            user_message=user_message,
            history=history,
            max_tokens=max_tokens,
            feature=feature,
        )
        if full:
            yield full
        else:
            yield f"[ERROR] {e}"


async def vision_chat_completion_stream(
    *,
    system_prompt: str,
    user_message: str,
    image_data_url: str,
    history: list[dict] | None = None,
    max_tokens: int = 800,
    feature: str | None = None,
) -> AsyncIterator[str]:
    """多模态流式输出"""
    cfg = _cfg()
    if not cfg["api_key"]:
        yield "[ERROR] DeepSeek API 未配置"
        return

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
    payload = {
        "model": cfg["vision_model"],
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    usage_acc: dict | None = None
    yielded_any = False

    try:
        async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
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
                    logger.error(f"LLM vision stream error {resp.status_code}: {body[:200]}")
                    _record_doubao(
                        api="chat.completions.vision.stream",
                        model=cfg["vision_model"],
                        usage=None,
                        stream=True,
                        ok=False,
                        feature=feature,
                    )
                    yield "[ERROR] DeepSeek 识图服务异常"
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
                        if isinstance(data.get("usage"), dict):
                            usage_acc = data["usage"]
                        choices = data.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {}) or {}
                        text = delta.get("content", "")
                        if text:
                            yielded_any = True
                            yield text
                    except Exception:
                        continue
        if yielded_any or usage_acc:
            _record_doubao(
                api="chat.completions.vision.stream",
                model=cfg["vision_model"],
                usage=usage_acc,
                stream=True,
                feature=feature,
            )
    except Exception as e:
        logger.error(f"LLM vision stream failed: {e}")
        full = await vision_chat_completion(
            system_prompt=system_prompt,
            user_message=user_message,
            image_data_url=image_data_url,
            history=history,
            max_tokens=max_tokens,
            feature=feature,
        )
        if full:
            yield full
        else:
            yield f"[ERROR] {e}"
