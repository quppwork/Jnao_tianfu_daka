"""执行保障层 — 刹车 / 气囊 / 黑匣子。

实现 GuardPolicy 契约；由 assemble 注入 runtime。
"""

from app.harness.guards.budget import BudgetGuard
from app.harness.guards.circuit_breaker import CircuitBreakerGuard
from app.harness.guards.composite import CompositeGuard, default_guards
from app.harness.guards.permissions import PermissionsGuard
from app.harness.guards.timeout import TimeoutGuard
from app.harness.guards.trace_recorder import TraceRecorderGuard

__all__ = [
    "BudgetGuard",
    "CircuitBreakerGuard",
    "CompositeGuard",
    "PermissionsGuard",
    "TimeoutGuard",
    "TraceRecorderGuard",
    "default_guards",
]
