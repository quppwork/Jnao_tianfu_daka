"""首页引导 Agent — 进页开场 +（后续）只读工具对话。

分层约定：
- agents/guide/*  : 人设、情境、决策、开场编排、只读工具
- services/guide_service.py : HTTP/DB 会话持久化，调用本包对外入口
- api/guide.py    : 路由，不写业务
"""

from app.agents.guide.persona import SYSTEM_PROMPT

__all__ = [
    "SYSTEM_PROMPT",
    "build_guide_context",
    "resolve_situation",
    "run_bootstrap",
]

def __getattr__(name: str):
    # 延迟导入，避免环依赖；结构搭好后由各模块提供实现
    if name == "build_guide_context":
        from app.agents.guide.context import build_guide_context
        return build_guide_context
    if name == "resolve_situation":
        from app.agents.guide.situations import resolve_situation
        return resolve_situation
    if name == "run_bootstrap":
        from app.agents.guide.bootstrap import run_bootstrap
        return run_bootstrap
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
