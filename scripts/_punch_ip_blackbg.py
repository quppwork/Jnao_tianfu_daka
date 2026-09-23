"""Remove backdrop from IP PNGs via edge flood-fill (keeps dark hair)."""
from __future__ import annotations

import shutil
from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / "vue_fronted" / "src" / "static" / "dayu" / "assets" / "ip"
NAMES = ["sizhe.png", "dezhe.png", "xingzhe.png", "xuezhe.png", "yingzhe.png"]
# treat as backdrop if max(rgb) below this AND reachable from image edge
BG_MAX = 48


def is_bg(r: int, g: int, b: int, a: int) -> bool:
    if a < 8:
        return True
    return max(r, g, b) <= BG_MAX


def punch(path: Path) -> tuple[int, int]:
    bak = path.with_suffix(".png.bak_blackbg")
    if not bak.exists():
        shutil.copy2(path, bak)
    # always re-punch from original backup
    im = Image.open(bak).convert("RGBA")
    w, h = im.size
    px = im.load()
    seen = [[False] * w for _ in range(h)]
    q: deque[tuple[int, int]] = deque()

    def try_push(x: int, y: int) -> None:
        if x < 0 or y < 0 or x >= w or y >= h or seen[y][x]:
            return
        r, g, b, a = px[x, y]
        if not is_bg(r, g, b, a):
            return
        seen[y][x] = True
        q.append((x, y))

    for x in range(w):
        try_push(x, 0)
        try_push(x, h - 1)
    for y in range(h):
        try_push(0, y)
        try_push(w - 1, y)

    cleared = 0
    while q:
        x, y = q.popleft()
        px[x, y] = (0, 0, 0, 0)
        cleared += 1
        try_push(x + 1, y)
        try_push(x - 1, y)
        try_push(x, y + 1)
        try_push(x, y - 1)

    im.save(path, optimize=True)
    return cleared, w * h


def main() -> None:
    for name in NAMES:
        path = ROOT / name
        if not path.exists():
            print("missing", path)
            continue
        cleared, total = punch(path)
        print(f"{name}: cleared {cleared}/{total} ({100 * cleared / total:.1f}%)")


if __name__ == "__main__":
    main()
