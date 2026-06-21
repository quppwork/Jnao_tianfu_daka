"""真实 AI 代理 — 连接 tianfu_rag"""

import json
from typing import AsyncIterator

import httpx

from config import load_settings


class AiProxyReal:
    async def proxy_talent_stream(
        self,
        message: str,
        user_id: str = "mobile_user",
        history: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        settings = load_settings()
        url = f"{settings['upstream']['tianfu_rag']['url']}/chat/stream"
        timeout = settings["upstream"]["tianfu_rag"]["timeout"]

        body = {
            "message": message,
            "user_id": user_id,
            "history": history or [],
            "temperature": 0.7,
            "stream_fast_mode": True,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=body, headers={"Content-Type": "application/json"}) as resp:
                resp.raise_for_status()
                buffer = ""
                async for chunk in resp.aiter_bytes():
                    buffer += chunk.decode("utf-8", errors="replace")
                    lines = buffer.split("\n")
                    buffer = lines.pop() or ""
                    for line in lines:
                        if line.startswith("data: "):
                            try:
                                yield json.loads(line[6:])
                            except json.JSONDecodeError:
                                continue

    async def check_health(self) -> bool:
        settings = load_settings()
        url = f"{settings['upstream']['tianfu_rag']['url']}/health"
        timeout = settings["upstream"]["tianfu_rag"]["health_timeout"]
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url)
                return resp.status_code == 200
        except Exception:
            return False

    async def chat(
        self,
        message: str,
        user_id: str = "mobile_user",
        user_department: str = "",
        history: list[dict] | None = None,
    ) -> dict:
        """非流式对话 — 返回 {answer, sources, answer_mode}"""
        settings = load_settings()
        url = f"{settings['upstream']['tianfu_rag']['url']}/chat"
        timeout = settings["upstream"]["tianfu_rag"]["timeout"]

        body = {
            "message": message,
            "user_id": user_id,
            "user_department": user_department,
            "hybrid_expert_mode": False,
            "rag_architecture": "auto",
            "history": history or [],
        }

        async with httpx.AsyncClient(timeout=min(timeout, 60.0)) as client:
            resp = await client.post(url, json=body, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            return resp.json()

    async def quick_respond(self, question: str, answer: str) -> str:
        """每道题后的简短自然回应 — 调 DeepSeek flash，3s 超时"""
        import asyncio as _asyncio
        settings = load_settings()
        ds = settings.get("deepseek", {})
        api_key = ds.get("api_key", "")
        model = ds.get("model", "deepseek-v4-flash")
        timeout = ds.get("timeout", 3.0)

        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是天赋测试助理。用户每答一题你给一句20字以内的自然回应，不要分析、不要评价、不要提问。"},
                {"role": "user", "content": f"题目：{question}\n用户回答：{answer}\n简短回应（20字内）："},
            ],
            "max_tokens": 40,
            "temperature": 0.7,
        }

        try:
            async with httpx.AsyncClient(timeout=min(timeout, 3.0)) as client:
                resp = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    text = data["choices"][0]["message"]["content"].strip()
                    # 超过 40 字直接截断
                    if len(text) > 40:
                        return "对不起这个问题有点超纲了呢"
                    return text
                return "好的，我们继续下一题～"
        except Exception:
            return "好的，我们继续下一题～"

    async def generate_report_summary(
        self,
        test_type: str,
        dimensions: list[dict],
        scores: list[dict],
    ) -> str | None:
        settings = load_settings()
        url = f"{settings['upstream']['tianfu_rag']['url']}/chat"
        timeout = settings["upstream"]["tianfu_rag"]["timeout"]

        dims_text = "\n".join(
            f"- {d['label']}: {d['score']}分" for d in scores
        )
        prompt = (
            f"你是一位天赋测评解读专家。请根据以下{test_type}天赋测评的维度得分，"
            f"生成一段200字以内的报告摘要：\n\n{dims_text}\n\n"
            f"请用温暖、鼓励的语气，突出被测者的核心优势。"
        )

        try:
            async with httpx.AsyncClient(timeout=min(timeout, 30.0)) as client:
                resp = await client.post(
                    url,
                    json={
                        "message": prompt,
                        "user_id": "dev_report",
                        "temperature": 0.5,
                        "max_tokens_answer": 400,
                    },
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("answer", "").strip() or None
                return None
        except Exception:
            return None
