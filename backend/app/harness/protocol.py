"""沙箱数据面协议 — 宿主只收结构化结果，不碰沙箱文件系统/进程。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ExecStatus = Literal["success", "error", "denied", "timeout", "cancelled"]

MAX_RESULT_BYTES_DEFAULT = 65536
DENIED_TOOLS = frozenset({"python", "shell", "bash", "cmd", "powershell", "sh"})


@dataclass
class ToolCall:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 20_000
    files: list[dict[str, str]] = field(default_factory=list)
    call_id: str = ""

    def to_exec_msg(self) -> dict[str, Any]:
        return {
            "op": "exec",
            "id": self.call_id,
            "tool": self.tool,
            "args": self.args,
            "timeout_ms": self.timeout_ms,
            "files": self.files,
        }


@dataclass
class ExecResult:
    status: ExecStatus
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, str]] = field(default_factory=list)
    duration_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "data": self.data,
            "artifacts": self.artifacts,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }

    @property
    def ok(self) -> bool:
        return self.status == "success"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ExecResult:
        status = str(raw.get("status") or "error")
        if status not in ("success", "error", "denied", "timeout", "cancelled"):
            status = "error"
        return cls(
            status=status,  # type: ignore[arg-type]
            exit_code=int(raw.get("exit_code") or 0),
            stdout=str(raw.get("stdout") or ""),
            stderr=str(raw.get("stderr") or ""),
            data=raw.get("data") if isinstance(raw.get("data"), dict) else {},
            artifacts=list(raw.get("artifacts") or []),
            duration_ms=int(raw.get("duration_ms") or 0),
            error=raw.get("error"),
        )


def clip_text(text: str, limit: int) -> str:
    raw = text or ""
    encoded = raw.encode("utf-8")
    if len(encoded) <= limit:
        return raw
    return encoded[: max(0, limit - 3)].decode("utf-8", errors="ignore") + "..."
