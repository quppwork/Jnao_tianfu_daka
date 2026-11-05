# -*- coding: utf-8 -*-
"""Rewrite relative assets/... paths in dayu HTML to /static/dayu/assets/..."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "vue_fronted" / "src" / "static" / "dayu" / "html"

# Match assets/ that is NOT already preceded by /static/dayu/
# Covers: 'assets/', "assets/", `assets/, url(assets/, url('assets/, &#39;assets/
PAT = re.compile(
    r"(?<!/static/dayu/)"  # negative lookbehind for absolute prefix
    r"(assets/[A-Za-z0-9_./\-]+)"
)


def fix_text(text: str) -> tuple[str, int]:
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        count += 1
        return "/static/dayu/" + m.group(1)

    return PAT.sub(repl, text), count


def main() -> None:
    total = 0
    for path in sorted(ROOT.glob("*.html")):
        raw = path.read_text(encoding="utf-8")
        new, n = fix_text(raw)
        if n:
            path.write_text(new, encoding="utf-8", newline="\n")
            print(f"{path.name}: {n} replacements")
            total += n
        else:
            print(f"{path.name}: ok")
    print(f"TOTAL: {total}")

    # verify remaining relative refs
    print("\n--- remaining relative assets/ ---")
    for path in sorted(ROOT.glob("*.html")):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            tmp = line
            while "/static/dayu/assets/" in tmp:
                tmp = tmp.replace("/static/dayu/assets/", "", 1)
            if "assets/" in tmp:
                print(f"{path.name}:{i}: {line.strip()[:140]}")


if __name__ == "__main__":
    main()
