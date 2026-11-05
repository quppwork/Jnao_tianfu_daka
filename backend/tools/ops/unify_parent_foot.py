# -*- coding: utf-8 -*-
"""Unify parent Dayu bottom tab bar (size/position) like student shell."""
from __future__ import annotations
import re
from pathlib import Path

HTML_DIR = Path(r"d:/daka/Jnao_tianfu_daka/vue_fronted/src/static/dayu/html")
PARENT_PAGES = [
    "parent.html",
    "community.html",
    "consult.html",
    "pdata.html",
    "pset.html",
    "pcourse.html",
]

# Keep parent gold active; match student geometry
FOOT_BLOCK = (
    ".foot{position:fixed;bottom:0;left:0;right:0;width:100%;"
    "max-width:var(--app-max-width, 480px);margin:0 auto;"
    "background:rgba(13,17,31,.96);backdrop-filter:blur(12px);"
    "border-top:1px solid #232B3D;"
    "padding:8px 10px calc(8px + env(safe-area-inset-bottom, 0px));"
    "display:flex;justify-content:space-around;z-index:50;box-sizing:border-box}"
    ".foot a{text-align:center;color:#8B93A5;font-size:11px;flex:1;"
    "text-decoration:none;padding:0}"
    ".foot a.on{color:#F5D9A8;font-weight:700}"
    ".foot a img{width:38px;height:38px;object-fit:contain;display:block;margin:0 auto 1px}"
)

PHONE_CANON = (
    ".phone{width:100%;max-width:var(--app-max-width, 480px);margin:0 auto;"
    "min-height:100vh;min-height:100dvh;height:100vh;height:100dvh;"
    "padding-bottom:110px;box-sizing:border-box;"
    "overflow-x:hidden;overflow-y:auto;-webkit-overflow-scrolling:touch;"
    "scrollbar-width:none;-ms-overflow-style:none}"
    ".phone::-webkit-scrollbar{display:none;width:0;height:0}"
)

ASKBAR_CANON = (
    ".askbar{position:fixed;bottom:72px;left:0;right:0;width:100%;"
    "max-width:var(--app-max-width, 480px);margin:0 auto;"
    "display:flex;gap:8px;padding:8px 14px;z-index:40;box-sizing:border-box}"
)

FOOT_RE = re.compile(
    r"\.foot\{[^}]+\}"
    r"(?:\.foot a\{[^}]+\})?"
    r"(?:\.foot a\.on\{[^}]+\})?"
    r"(?:\.foot a img\{[^}]+\})?"
)

PHONE_RE = re.compile(r"\.phone\{[^}]+\}")
ASKBAR_RE = re.compile(r"\.askbar\{[^}]+\}")


def patch_file(path: Path) -> None:
    t = path.read_text(encoding="utf-8")
    orig = t

    if FOOT_RE.search(t):
        t = FOOT_RE.sub(FOOT_BLOCK, t, count=1)
    else:
        print(f"  warn: no foot block in {path.name}")

    if PHONE_RE.search(t):
        t = PHONE_RE.sub(PHONE_CANON, t, count=1)
    else:
        # some pages use body padding only
        if "body{" in t and "overflow-y:auto" not in t[:800]:
            t = re.sub(
                r"(body\{[^}]*)\}",
                r"\1;overflow-x:hidden}",
                t,
                count=1,
            )

    if ASKBAR_RE.search(t):
        t = ASKBAR_RE.sub(ASKBAR_CANON, t, count=1)

    # inline 34px foot icons → 38
    t = re.sub(
        r'(class="foot"[\s\S]{0,1200}?style="width:)34px(;height:)34px',
        r"\g<1>38px\g<2>38px",
        t,
        count=1,
    )
    # any remaining foot img width 34 in style attrs near foot — simpler replace in whole file for foot icons only
    # Replace common pattern in foot section
    if '<div class="foot">' in t or "<div class=\"foot\">" in t:
        # after foot marker, replace 34px icons that are tab icons
        parts = t.split('<div class="foot">', 1)
        if len(parts) == 2:
            head, rest = parts
            # only within first 1500 chars of foot
            foot_end = rest.find("</div>")
            if foot_end > 0:
                foot = rest[:foot_end].replace("width:34px;height:34px", "width:38px;height:38px")
                rest = foot + rest[foot_end:]
            t = head + '<div class="foot">' + rest

    if t != orig:
        path.write_text(t, encoding="utf-8", newline="\n")
        print(f"patched {path.name}")
    else:
        print(f"unchanged {path.name}")


def main() -> None:
    for name in PARENT_PAGES:
        p = HTML_DIR / name
        if not p.exists():
            print(f"missing {name}")
            continue
        patch_file(p)


if __name__ == "__main__":
    main()
