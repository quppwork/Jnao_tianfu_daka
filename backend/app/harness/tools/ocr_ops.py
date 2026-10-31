"""Harness MCP · 题目 OCR（宿主 jnao-host）。

当前主用方：学科答疑。实现集中在此，业务门面只 call_tool，不直连百炼/DeepSeek。
优先 Qwen3.5-OCR（SOLVE_OCR_API_KEY / DASHSCOPE_API_KEY），其次 DeepSeek 识图，再否则 mock。
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

from app.harness.registry import register_tool
from app.harness.types import ToolSpec

# 答疑为主；harness 探测 / 拍题门面也可挂载
_OCR_PROFILES = ("qa", "harness", "solve_science", "solve_language", "solve_humanities", "solve_invention", "solve_arts")


def ocr_api_key() -> str:
    for name in ("SOLVE_OCR_API_KEY", "DASHSCOPE_API_KEY"):
        key = (os.getenv(name) or "").strip()
        if key and not key.startswith("your-"):
            return key
    return ""


def ocr_configured() -> bool:
    return bool(ocr_api_key())


def ocr_base_url() -> str:
    host = (os.getenv("BAILIAN_API_HOST") or os.getenv("SOLVE_OCR_API_HOST") or "").strip()
    if host:
        host = host.removeprefix("https://").removeprefix("http://").rstrip("/")
        return f"https://{host}/compatible-mode/v1"
    return "https://dashscope.aliyuncs.com/compatible-mode/v1"


def ocr_model_name() -> str:
    return (os.getenv("SOLVE_VL_MODEL") or "qwen3.5-ocr").strip() or "qwen3.5-ocr"


async def ocr_extract(args: dict[str, Any]) -> dict[str, Any]:
    """识别题目图片全文（含公式 LaTeX），不解题。"""
    import httpx

    b64 = str(args.get("image_base64") or "").strip()
    data_url = str(args.get("image_data_url") or "").strip()
    hint = str(args.get("subject_hint") or "").strip()
    custom = str(args.get("prompt") or "").strip()
    if not b64 and data_url.startswith("data:") and "," in data_url:
        b64 = data_url.split(",", 1)[1].strip()
    if not b64 and not data_url:
        return {"ok": False, "error": "需要 image_base64 或 image_data_url", "mock": False}

    prompt = custom or (
        "请完整识别图中题目全部文字与公式，保持编号与小问结构；"
        "数学公式用 LaTeX；不要解题、不要省略小问。"
    )
    if hint:
        prompt = f"学科提示：{hint}。{prompt}"

    max_tokens = int(args.get("max_tokens") or 1600)
    api_key = ocr_api_key()
    if api_key:
        if not data_url:
            data_url = f"data:image/jpeg;base64,{b64}"
        model = ocr_model_name()
        base = ocr_base_url()
        image_part: dict[str, Any] = {
            "type": "image_url",
            "image_url": {"url": data_url},
        }
        if "ocr" in model.lower():
            image_part["min_pixels"] = 3072
            image_part["max_pixels"] = 8388608
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(
                    f"{base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    image_part,
                                ],
                            }
                        ],
                        "max_tokens": max_tokens,
                    },
                )
            resp.raise_for_status()
            data = resp.json()
            text = (
                (((data.get("choices") or [{}])[0].get("message") or {}).get("content"))
                or ""
            ).strip()
            if text:
                return {
                    "ok": True,
                    "text": text,
                    "provider": "qwen-ocr" if "ocr" in model.lower() else "qwen-vl",
                    "model": model,
                    "mock": False,
                }
        except Exception:
            # 主 OCR 失败：继续走下方 vision 回退（仍在本工具内，不回业务门面）
            pass

    if not data_url and b64:
        data_url = f"data:image/jpeg;base64,{b64}"
    try:
        from app.services.doubao_client import is_configured, vision_chat_completion

        if is_configured() and data_url:
            text = await vision_chat_completion(
                system_prompt="你是 OCR 助手。完整识别题目文字与小问，不要解题。",
                user_message=prompt,
                image_data_url=data_url,
                max_tokens=max_tokens,
            )
            text = (text or "").strip()
            if text:
                return {
                    "ok": True,
                    "text": text,
                    "provider": "deepseek_vision",
                    "mock": False,
                }
    except Exception as e:
        return {"ok": False, "error": f"vision failed: {e}"[:240], "mock": False}

    digest = hashlib.md5((b64 or data_url or "x")[:80].encode("utf-8", "ignore")).hexdigest()[:8]
    return {
        "ok": True,
        "text": (
            f"【模拟 OCR】未配置 SOLVE_OCR_API_KEY / DeepSeek 识图。"
            f"示例题干：计算 1+1 等于多少？（ref={digest}）"
        ),
        "provider": "mock",
        "mock": True,
    }


# 兼容旧名：答疑曾用 vision_ocr
async def vision_ocr(args: dict[str, Any]) -> dict[str, Any]:
    return await ocr_extract(args)


_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "image_base64": {"type": "string", "description": "JPEG/PNG Base64"},
        "image_data_url": {"type": "string", "description": "data:image/...;base64,..."},
        "subject_hint": {"type": "string"},
        "prompt": {"type": "string", "description": "可选自定义识别提示"},
        "max_tokens": {"type": "integer"},
    },
    "additionalProperties": False,
}


def register() -> None:
    common = dict(
        input_schema=_INPUT_SCHEMA,
        permission="readonly",
        profiles=_OCR_PROFILES,
        plane="host",
        mcp_server="jnao-host",
    )
    register_tool(
        ToolSpec(
            name="ocr_extract",
            description="【jnao-host】题目图片 OCR（Qwen3.5-OCR 优先）：完整提取文字与公式 LaTeX，不解题。",
            handler=ocr_extract,
            **common,
        )
    )
    # 别名：历史调用 / 测试仍认 vision_ocr
    register_tool(
        ToolSpec(
            name="vision_ocr",
            description="题目图片 OCR（ocr_extract 别名）。",
            handler=vision_ocr,
            **common,
        )
    )
