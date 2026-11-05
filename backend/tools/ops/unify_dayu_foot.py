# -*- coding: utf-8 -*-
"""Unify student bottom tab bar (.foot) size/position across dayu pages."""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(r"d:/daka/Jnao_tianfu_daka/vue_fronted/src")

CANON_FOOT = (
    "position:fixed;bottom:0;left:50%;transform:translateX(-50%);"
    "width:100%;max-width:var(--app-max-width, 480px);"
    "background:rgba(11,14,20,.94);backdrop-filter:blur(12px);"
    "border-top:1px solid #232B3D;"
    "padding:8px 10px calc(8px + env(safe-area-inset-bottom, 0px));"
    "display:flex;justify-content:space-around;z-index:50;box-sizing:border-box"
)

CANON_FOOT_LT = (
    "position:fixed;bottom:0;left:50%;transform:translateX(-50%);"
    "width:100%;max-width:var(--app-max-width, 480px);"
    "background:rgba(235,238,244,.94);backdrop-filter:blur(12px);"
    "border-top:1px solid #c2cadc;"
    "padding:8px 10px calc(8px + env(safe-area-inset-bottom, 0px));"
    "display:flex;justify-content:space-around;z-index:50;box-sizing:border-box"
)


def replace_430(text: str) -> str:
    return text.replace("max-width:430px", "max-width:var(--app-max-width, 480px)").replace(
        "max-width: 430px", "max-width:var(--app-max-width, 480px)"
    )


def patch_style_css(path: Path) -> None:
    t = path.read_text(encoding="utf-8")
    t = replace_430(t)
    t = re.sub(
        r"\.foot\{[^}]+\}",
        ".foot{" + CANON_FOOT + "}",
        t,
        count=1,
    )
    # ensure fic rule
    if ".fic{" not in t.replace(" ", "") and ".foot a img" not in t:
        t = t.rstrip() + (
            "\n.foot a .fic,.fic{display:block;width:38px;height:38px;margin:0 auto 1px;object-fit:contain}\n"
            ".foot a img{width:38px;height:38px;object-fit:contain;display:block;margin:0 auto 1px}\n"
        )
    path.write_text(t, encoding="utf-8", newline="\n")
    print(f"patched {path.name}")


def patch_milestone(path: Path) -> None:
    t = path.read_text(encoding="utf-8")
    t = replace_430(t)
    # dark foot
    t = re.sub(
        r"\.foot\{position:fixed;left:0;right:0;bottom:0;[^}]+\}",
        ".foot{" + CANON_FOOT + "}",
        t,
        count=1,
    )
    # light foot that starts with .foot{position:fixed;bottom:0;left:0;right:0
    t = re.sub(
        r"\.foot\{position:fixed;bottom:0;left:0;right:0;[^}]+\}",
        ".foot{" + CANON_FOOT_LT + "}",
        t,
        count=1,
    )
    path.write_text(t, encoding="utf-8", newline="\n")
    print(f"patched {path.name}")


def patch_html_generic(path: Path) -> None:
    t = path.read_text(encoding="utf-8")
    orig = t
    t = replace_430(t)
    # normalize padding without safe-area on foot
    t = t.replace(
        "padding:8px 10px;display:flex;justify-content:space-around;z-index:50}",
        "padding:8px 10px calc(8px + env(safe-area-inset-bottom, 0px));display:flex;justify-content:space-around;z-index:50;box-sizing:border-box}",
    )
    t = t.replace(
        "padding:6px 4px calc(8px + env(safe-area-inset-bottom,0px))",
        "padding:8px 10px calc(8px + env(safe-area-inset-bottom, 0px))",
    )
    t = t.replace(
        "padding:6px 4px calc(8px + env(safe-area-inset-bottom, 0px))",
        "padding:8px 10px calc(8px + env(safe-area-inset-bottom, 0px))",
    )
    if t != orig:
        path.write_text(t, encoding="utf-8", newline="\n")
        print(f"updated {path.name}")
    else:
        print(f"ok {path.name}")


def patch_qa_vue(path: Path) -> None:
    t = path.read_text(encoding="utf-8")
    old = """.foot {
  flex-shrink: 0;
  width: 100%;
  max-width: var(--app-max-width, 480px);
  margin: 0 auto;
  background: rgba(11, 14, 20, 0.94);
  backdrop-filter: blur(12px);
  border-top: 1px solid #232b3d;
  padding: 8px 10px calc(8px + env(safe-area-inset-bottom, 0px));
  display: flex;
  justify-content: space-around;
  box-sizing: border-box;
}"""
    new = """.foot {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: var(--app-max-width, 480px);
  background: rgba(11, 14, 20, 0.94);
  backdrop-filter: blur(12px);
  border-top: 1px solid #232b3d;
  padding: 8px 10px calc(8px + env(safe-area-inset-bottom, 0px));
  display: flex;
  justify-content: space-around;
  z-index: 50;
  box-sizing: border-box;
}"""
    if old in t:
        t = t.replace(old, new)
        # ensure content not covered: inputbar needs bottom offset above foot
        if "padding-bottom: calc(56px" not in t and ".app {" in t:
            t = t.replace(
                """.app {
  height: 100vh;
  height: 100dvh;
  width: 100%;
  max-width: var(--app-max-width, 480px);
  margin: 0 auto;
  background: #0b0e14;
  color: #edebe4;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
}""",
                """.app {
  height: 100vh;
  height: 100dvh;
  width: 100%;
  max-width: var(--app-max-width, 480px);
  margin: 0 auto;
  background: #0b0e14;
  color: #edebe4;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
  padding-bottom: calc(64px + env(safe-area-inset-bottom, 0px));
}""",
            )
        path.write_text(t, encoding="utf-8", newline="\n")
        print("patched qa/dayu.vue foot → fixed")
    else:
        print("qa foot pattern not found / already fixed")


def main() -> None:
    patch_style_css(ROOT / "static/dayu/style.css")
    patch_milestone(ROOT / "static/dayu/html/milestone.html")
    patch_qa_vue(ROOT / "pages/qa/dayu.vue")
    for p in (ROOT / "static/dayu/html").glob("*.html"):
        if p.name == "milestone.html":
            continue
        patch_html_generic(p)
    # training fic display block consistency
    train = ROOT / "pages/training/dayu.vue"
    tt = train.read_text(encoding="utf-8")
    if ".fic { width: 38px; height: 38px; margin-bottom: 1px; }" in tt:
        tt = tt.replace(
            ".fic { width: 38px; height: 38px; margin-bottom: 1px; }",
            ".fic { display: block; width: 38px; height: 38px; margin: 0 auto 1px; }",
        )
        train.write_text(tt, encoding="utf-8", newline="\n")
        print("patched training fic")


if __name__ == "__main__":
    main()
