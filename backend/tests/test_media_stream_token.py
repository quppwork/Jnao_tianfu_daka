"""媒体流短期签名"""

from app.core.media_stream_token import (
    append_media_stream_token,
    make_media_stream_token,
    verify_media_stream_token,
)


def test_media_stream_token_roundtrip():
    tok = make_media_stream_token(42, 7, "video")
    assert verify_media_stream_token(tok, 42, 7, "video")
    assert not verify_media_stream_token(tok, 43, 7, "video")
    assert not verify_media_stream_token(tok, 42, 7, "audio")


def test_append_media_stream_token():
    url = append_media_stream_token("/api/training/items/1/stream?media=video", 1, 2, "video")
    assert "mt=" in url
    assert url.startswith("/api/training/items/1/stream")
