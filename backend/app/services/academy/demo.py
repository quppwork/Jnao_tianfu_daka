"""正片和观看记录还没接上时的模拟数据。

有真实 OSS key 或用户自己的观看记录后，同一集以真实数据为准。
模拟数据不进角色提示词，也不进 git 视频文件。
"""

from __future__ import annotations

DEMO_WATCHED_IDS = tuple(f"E{n:02d}" for n in range(1, 13))
DEMO_MEDIA_IDS = frozenset(f"E{n:02d}" for n in range(1, 15)) | frozenset({"EH01"})

CAMP = {
    "title": "超脑训练营 · 四天三夜",
    "enrolled": 183,
    "seats_left": 7,
    "seats_total": 190,
    "price": "3980",
    "list_price": "5980",
    "open": False,
    "note": "报名通道尚未开通（席位为模拟数据）",
}


def media_kind(episode_id: str, oss_key: str) -> str:
    if (oss_key or "").strip():
        return "oss"
    if episode_id in DEMO_MEDIA_IDS:
        return "demo"
    return "none"
