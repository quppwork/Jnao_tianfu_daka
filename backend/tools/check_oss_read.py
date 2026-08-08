#!/usr/bin/env python3
"""Quick OSS connectivity check — list + head + small read."""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
sys.path.insert(0, _BACKEND)
os.chdir(_BACKEND)

from dotenv import load_dotenv

load_dotenv(os.path.join(_BACKEND, ".env"), override=True)
_prod = os.path.join(_BACKEND, "..", ".env.production")
if os.path.isfile(_prod):
    load_dotenv(_prod, override=False)

from app.services.oss_client import (
    _bucket_client,
    _oss_cfg,
    is_oss_configured,
    list_audio_objects,
    list_video_objects,
)


def main() -> int:
    cfg = _oss_cfg()
    print("=== OSS Config ===")
    print("configured:", is_oss_configured())
    print("bucket:", cfg["bucket"])
    print("endpoint:", cfg["endpoint"])
    print("prefixes:", cfg.get("prefixes"))
    print("access_key_id set:", bool(cfg["access_key_id"]))
    print("access_key_secret set:", bool(cfg["access_key_secret"]))

    if not is_oss_configured():
        print("FAIL: OSS keys missing")
        return 1

    audio: list = []
    videos: list = []

    try:
        audio = list_audio_objects()
        print("\n=== Audio (yinpin/) ===")
        print("total:", len(audio))
        for row in audio[:3]:
            print(" sample:", row["key"], "size=", row["size"])
    except Exception as e:
        print("\nAUDIO LIST ERROR:", type(e).__name__, str(e)[:200])

    try:
        videos = list_video_objects("shipin/")
        print("\n=== Video (shipin/) ===")
        print("total:", len(videos))
        for row in videos[:3]:
            print(" sample:", row["key"], "size=", row["size"])
    except Exception as e:
        print("\nVIDEO LIST ERROR:", type(e).__name__, str(e)[:200])

    try:
        bucket = _bucket_client()
        sample = audio[0] if audio else (videos[0] if videos else None)
        if not sample:
            print("\nSKIP read test: no media objects found")
            return 0
        key = sample["key"]
        meta = bucket.head_object(key)
        print("\n=== Read test (head_object + range read) ===")
        print("key:", key)
        print("content_length:", meta.content_length)
        print("content_type:", meta.headers.get("Content-Type"))
        result = bucket.get_object(key, byte_range=(0, 1023))
        chunk = result.read(64)
        result.close()
        print("first_bytes_ok:", len(chunk) > 0, "len=", len(chunk))
        print("\nOK: OSS readable")
        return 0
    except Exception as e:
        print("\nREAD ERROR:", type(e).__name__, str(e)[:300])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
