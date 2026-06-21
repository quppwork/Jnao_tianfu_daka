"""JNAO external API client — backend-to-backend via httpx"""

import httpx
from typing import Any

JNAO_BASE = "https://m.jnao.com"
TIMEOUT = 15.0


async def jnao_submit(answer_bits: str, uid: int, test_type: int) -> str:
    """Submit 35-bit answer string to JNAO, returns record ID."""
    params = {"answer": answer_bits, "uid": uid, "type": test_type}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{JNAO_BASE}/h5/adult/submitanswer", params=params)
        resp.raise_for_status()
        data = resp.json()
    code = data.get("code")
    if code not in (1, 10):
        raise RuntimeError(data.get("msg") or f"JNAO submit failed (code {code})")
    return data["data"]["id"]


async def jnao_get_report(record_id: str) -> dict[str, Any]:
    """Fetch full talent report JSON by record ID."""
    params = {"id": record_id}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{JNAO_BASE}/h5/Adult/testresult", params=params)
        resp.raise_for_status()
        data = resp.json()
    if data.get("code") != 1:
        raise RuntimeError(data.get("msg") or f"JNAO report fetch failed (code {data.get('code')})")
    return data["data"]
