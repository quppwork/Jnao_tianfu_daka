"""拍题图片压缩：最长边 1600px，JPEG 85%。"""

from __future__ import annotations

import base64
import io


def compress_image_bytes(
    raw: bytes,
    *,
    max_side: int = 1600,
    quality: int = 85,
) -> tuple[bytes, str]:
    """返回 (jpeg_bytes, data_url)。Pillow 不可用时原样包 data URL。"""
    if not raw:
        raise ValueError("空图片")
    try:
        from PIL import Image
    except ImportError:
        b64 = base64.b64encode(raw).decode("ascii")
        return raw, f"data:image/jpeg;base64,{b64}"

    img = Image.open(io.BytesIO(raw))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    elif img.mode == "L":
        img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, float(max_side) / float(max(w, h) or 1))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=int(quality), optimize=True)
    data = buf.getvalue()
    b64 = base64.b64encode(data).decode("ascii")
    return data, f"data:image/jpeg;base64,{b64}"
