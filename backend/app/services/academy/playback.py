"""播放地址。OSS 签名与模拟片分开，调用方只看 media。"""

from __future__ import annotations

from app.agents.academy.catalog import Episode
from app.services.academy.demo import media_kind
from app.services.oss_client import public_url, sign_cdn_play_url


def kind_of(episode: Episode) -> str:
    return media_kind(episode.id, episode.oss_key)


def play_url(episode: Episode) -> str | None:
    if kind_of(episode) != "oss":
        return None
    key = episode.oss_key.strip()
    raw = key if key.startswith("http") else public_url(key)
    return sign_cdn_play_url(raw) or raw


def duration_label(episode: Episode) -> str:
    if episode.duration_label:
        return episode.duration_label
    if kind_of(episode) == "demo":
        return "模拟正片"
    return "正片待上传"
