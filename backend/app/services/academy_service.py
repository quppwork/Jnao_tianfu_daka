"""兼容入口：请优先 `from app.services.academy import …`。"""

from app.services.academy import AcademyError, chat, get_sector, open_room, report_progress

__all__ = [
    "AcademyError",
    "chat",
    "get_sector",
    "open_room",
    "report_progress",
]
