"""控制面：创建 / 健康检查 / 取消 / 销毁。Docker CLI 只在宿主侧，不进沙箱、不挂 docker.sock。"""

from __future__ import annotations

import json
import logging
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from app.harness.audit import audit_control
from app.harness.protocol import ExecResult, ToolCall, clip_text
from app.harness.settings import HarnessSettings, load_harness_settings

logger = logging.getLogger("jnao.harness.control")

_AGENT = Path(__file__).resolve().parents[2] / "scripts" / "harness_sandbox_agent.py"


class SandboxError(RuntimeError):
    pass


def _settings() -> HarnessSettings:
    return load_harness_settings()


def _sandbox_env() -> dict[str, str]:
    keep = (
        "PATH",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "TMP",
        "TEMP",
        "LOCALAPPDATA",
        "PYTHONHOME",
        "HOME",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "LANG",
        "LC_ALL",
    )
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["JNAO_SANDBOX"] = "1"
    return env


@dataclass
class SandboxSession:
    id: str
    token: str
    runtime: str
    created_at: float
    allow_tools: tuple[str, ...] = ("sandbox.ping", "sandbox.health")
    workspace: str | None = None
    proc: subprocess.Popen[str] | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


class SandboxController:
    def __init__(self) -> None:
        self._sessions: dict[str, SandboxSession] = {}
        self._lock = threading.Lock()
        self._shared_id: str | None = None

    def create(self) -> SandboxSession:
        cfg = _settings()
        sid = uuid.uuid4().hex[:12]
        token = secrets.token_urlsafe(16)
        if cfg.sandbox == "docker":
            sess = SandboxSession(
                id=sid, token=token, runtime="docker", created_at=time.time()
            )
            with self._lock:
                self._sessions[sid] = sess
            audit_control("create", session_id=sid, extra={"runtime": "docker"})
            return sess
        if not _AGENT.is_file():
            raise SandboxError("sandbox agent missing")
        work = tempfile.mkdtemp(prefix=f"jnao-sbx-{sid}-")
        try:
            proc = subprocess.Popen(
                [sys.executable, "-u", str(_AGENT), "--loop"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=work,
                env=_sandbox_env(),
                text=True,
                bufsize=1,
            )
        except Exception:
            shutil.rmtree(work, ignore_errors=True)
            raise
        sess = SandboxSession(
            id=sid,
            token=token,
            runtime="local",
            created_at=time.time(),
            workspace=work,
            proc=proc,
        )
        with self._lock:
            self._sessions[sid] = sess
        audit_control("create", session_id=sid, extra={"runtime": "local", "pid": proc.pid})
        return sess

    def get(self, session_id: str) -> SandboxSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        now = time.time()
        rows = []
        for s in list(self._sessions.values()):
            alive = True
            if s.runtime == "local":
                alive = bool(s.proc) and s.proc.poll() is None
            rows.append(
                {
                    "id": s.id,
                    "runtime": s.runtime,
                    "alive": alive,
                    "age_s": int(now - s.created_at),
                }
            )
        return rows

    def health(self, sess: SandboxSession) -> ExecResult:
        if sess.runtime == "docker":
            return ExecResult(status="success", data={"alive": True, "runtime": "docker"})
        proc = sess.proc
        if proc is None or proc.poll() is not None:
            return ExecResult(status="error", error="sandbox process dead", exit_code=1)
        return self.exec(
            sess,
            ToolCall(tool="sandbox.health", args={}, timeout_ms=3000, call_id="health"),
        )

    def exec(self, sess: SandboxSession, call: ToolCall) -> ExecResult:
        cfg = _settings()
        if call.tool not in sess.allow_tools:
            return ExecResult(
                status="denied",
                exit_code=126,
                error=f"tool {call.tool} not in session allowlist",
            )
        timeout_s = max(0.5, min(call.timeout_ms / 1000.0, cfg.sandbox_timeout_s))
        if sess.runtime == "docker":
            return _docker_oneshot(call, timeout_s, cfg)
        return _local_rpc(sess, call, timeout_s, cfg.max_result_bytes)

    def cancel(self, sess: SandboxSession) -> None:
        audit_control("cancel", session_id=sess.id)
        proc = sess.proc
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

    def destroy(self, sess: SandboxSession) -> None:
        audit_control("destroy", session_id=sess.id, extra={"runtime": sess.runtime})
        self.cancel(sess)
        proc = sess.proc
        if proc:
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    if stream:
                        stream.close()
                except Exception:
                    pass
        if sess.workspace:
            shutil.rmtree(sess.workspace, ignore_errors=True)
        with self._lock:
            self._sessions.pop(sess.id, None)
            if self._shared_id == sess.id:
                self._shared_id = None

    def shared(self) -> SandboxSession:
        with self._lock:
            if self._shared_id and self._shared_id in self._sessions:
                sess = self._sessions[self._shared_id]
                if sess.runtime == "docker" or (
                    sess.proc is not None and sess.proc.poll() is None
                ):
                    return sess
        sess = self.create()
        with self._lock:
            self._shared_id = sess.id
        return sess


def _local_rpc(
    sess: SandboxSession,
    call: ToolCall,
    timeout_s: float,
    max_bytes: int,
) -> ExecResult:
    proc = sess.proc
    if proc is None or proc.stdin is None or proc.stdout is None:
        return ExecResult(status="error", error="sandbox stdin/stdout missing", exit_code=1)
    if proc.poll() is not None:
        err = ""
        if proc.stderr:
            err = proc.stderr.read()[:500]
        return ExecResult(status="error", error=err or "sandbox exited", exit_code=proc.returncode or 1)
    msg = call.to_exec_msg()
    line = json.dumps(msg, ensure_ascii=False) + "\n"
    with sess._lock:
        try:
            proc.stdin.write(line)
            proc.stdin.flush()
        except BrokenPipeError:
            return ExecResult(status="error", error="sandbox pipe closed", exit_code=1)
        try:
            raw = _readline_timeout(proc.stdout, timeout_s)
        except TimeoutError:
            sess.proc and _kill(proc)
            return ExecResult(status="timeout", error=f"exec timeout {timeout_s}s", exit_code=124)
    if not raw:
        return ExecResult(status="error", error="empty executor response", exit_code=1)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return ExecResult(status="error", error="executor returned invalid json", exit_code=1)
    result = ExecResult.from_dict(payload if isinstance(payload, dict) else {})
    result.stdout = clip_text(result.stdout, max_bytes)
    result.stderr = clip_text(result.stderr, min(max_bytes, 8192))
    return result


def _readline_timeout(stream: TextIO, timeout_s: float) -> str:
    # Windows 上 stdout 管道 readline 无原生超时；用线程等一行。
    box: list[str] = []
    err: list[BaseException] = []

    def _read() -> None:
        try:
            box.append(stream.readline())
        except BaseException as e:
            err.append(e)

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        raise TimeoutError()
    if err:
        raise err[0]
    return box[0] if box else ""


def _kill(proc: subprocess.Popen[str]) -> None:
    try:
        proc.kill()
    except Exception:
        pass


def _docker_oneshot(call: ToolCall, timeout_s: float, cfg: HarnessSettings) -> ExecResult:
    docker = shutil.which("docker")
    if not docker:
        raise SandboxError("docker 不在 PATH；本地请用 HARNESS_SANDBOX=local")
    # 控制面在宿主调 Docker API/CLI；不把 docker.sock 映射进沙箱。
    cmd = [
        docker,
        "run",
        "--rm",
        "-i",
        "--network",
        "none",
        "--memory",
        f"{cfg.sandbox_memory_mb}m",
        "--pids-limit",
        str(cfg.sandbox_pids),
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=16m",
        cfg.sandbox_image,
    ]
    payload = json.dumps(call.to_exec_msg(), ensure_ascii=False).encode("utf-8")
    try:
        proc = subprocess.run(
            cmd,
            input=payload,
            capture_output=True,
            timeout=timeout_s + 8,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ExecResult(status="timeout", error=f"docker sandbox timeout {timeout_s}s", exit_code=124)
    if proc.returncode != 0 and not proc.stdout:
        err = (proc.stderr or b"").decode("utf-8", errors="replace")[:400]
        raise SandboxError(err or f"docker sandbox exit {proc.returncode}")
    raw = (proc.stdout or b"").decode("utf-8", errors="replace").strip().splitlines()
    if not raw:
        return ExecResult(status="error", error="docker executor empty stdout", exit_code=1)
    try:
        body = json.loads(raw[-1])
    except json.JSONDecodeError:
        return ExecResult(status="error", error="docker executor invalid json", exit_code=1)
    result = ExecResult.from_dict(body if isinstance(body, dict) else {})
    result.stdout = clip_text(result.stdout, cfg.max_result_bytes)
    return result


controller = SandboxController()
