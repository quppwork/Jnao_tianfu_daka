"""本地 Cursor / Claude：在 backend 目录执行 python -m app.harness.mcp_stdio"""

from __future__ import annotations

import asyncio
import json
import sys

from app.harness.mcp_protocol import handle_rpc


def _read_message() -> dict | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        if b":" in line:
            k, v = line.decode("utf-8", errors="replace").split(":", 1)
            headers[k.strip().lower()] = v.strip()
    n = int(headers.get("content-length") or "0")
    if n <= 0:
        return None
    raw = sys.stdin.buffer.read(n)
    return json.loads(raw.decode("utf-8"))


def _write_message(payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


async def _loop() -> None:
    while True:
        msg = await asyncio.to_thread(_read_message)
        if msg is None:
            return
        reply = await handle_rpc(msg)
        if reply is not None:
            _write_message(reply)


def main() -> None:
    asyncio.run(_loop())


if __name__ == "__main__":
    main()
