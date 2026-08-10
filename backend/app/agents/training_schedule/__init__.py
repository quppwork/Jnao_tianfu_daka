"""今日训练排课 Agent — 只读工具循环出技能草案；禁止写 Tier/OSS/DB。

与 Guide / QA 互不 import runner；落库仍由 services 校验投影后走规则路径。
"""

from app.agents.training_schedule.runner import run_schedule_assist

__all__ = ["run_schedule_assist"]
