"""天赋学院对外入口。

目录和角色在 agents.academy；本包只做进度、讨论落库和三页组装。
页面不要绕过这里去读表。
"""

from app.services.academy.errors import AcademyError
from app.services.academy.progress import report as report_progress
from app.services.academy.room import chat, open_room
from app.services.academy.sector import get_sector
from app.agents.academy.talk import sticker_pack

__all__ = [
    "AcademyError",
    "chat",
    "get_sector",
    "open_room",
    "report_progress",
    "sticker_pack",
]
