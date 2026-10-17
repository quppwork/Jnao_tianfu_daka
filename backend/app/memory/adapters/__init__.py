"""按 domain 拆分的 ThreadStore 适配器。"""

from app.memory.adapters.guide import GuideThreadAdapter
from app.memory.adapters.qa import QaThreadAdapter
from app.memory.adapters.report_talent import ReportTalentThreadAdapter

__all__ = [
    "GuideThreadAdapter",
    "QaThreadAdapter",
    "ReportTalentThreadAdapter",
]
