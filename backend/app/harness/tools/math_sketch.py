"""数学建模草图 — 根据题意生成简易 SVG（函数曲线 / 椭圆 / 坐标系点）。

不依赖 matplotlib；可选 sympy 采样。前端用 ```jnao-svg 围栏渲染。
"""

from __future__ import annotations

import math
from typing import Any
from xml.sax.saxutils import escape

from app.harness.registry import register_tool
from app.harness.types import ToolSpec

_PROFILES = ("qa", "solve_science")


def _esc(s: str) -> str:
    return escape(str(s or ""), {"\"": "&quot;"})


def _sample_expr(expr: str, x0: float, x1: float, n: int = 80) -> list[tuple[float, float]]:
    try:
        import sympy

        x = sympy.symbols("x")
        f = sympy.sympify(expr)
        xs = [x0 + (x1 - x0) * i / max(n - 1, 1) for i in range(n)]
        pts: list[tuple[float, float]] = []
        for xv in xs:
            try:
                yv = float(f.subs(x, xv).evalf())
                if math.isfinite(yv):
                    pts.append((xv, yv))
            except Exception:
                continue
        return pts
    except Exception:
        return []


def _svg_frame(w: int, h: int, body: str, caption: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{_esc(caption)}">'
        f'<rect width="100%" height="100%" rx="10" fill="#0f1724"/>'
        f"{body}"
        f'<text x="12" y="{h - 10}" fill="#8b93a5" font-size="11">{_esc(caption)}</text>'
        f"</svg>"
    )


def _axes(ox: float, oy: float, w: int, h: int, pad: int = 36) -> str:
    return (
        f'<line x1="{pad}" y1="{oy}" x2="{w - pad}" y2="{oy}" stroke="#3d4a63" stroke-width="1.2"/>'
        f'<line x1="{ox}" y1="{pad}" x2="{ox}" y2="{h - pad}" stroke="#3d4a63" stroke-width="1.2"/>'
        f'<text x="{w - pad - 8}" y="{oy - 6}" fill="#6ec8e0" font-size="11">x</text>'
        f'<text x="{ox + 6}" y="{pad + 12}" fill="#6ec8e0" font-size="11">y</text>'
    )


def sketch_plot(args: dict[str, Any]) -> dict[str, Any]:
    expr = str(args.get("expr") or args.get("expression") or "").strip()
    if not expr:
        return {"ok": False, "error": "需要 expr，如 sin(x) 或 x**2"}
    x0 = float(args.get("x_min", -5))
    x1 = float(args.get("x_max", 5))
    if x1 <= x0:
        x0, x1 = -5.0, 5.0
    pts = _sample_expr(expr, x0, x1)
    if len(pts) < 2:
        return {"ok": False, "error": f"无法采样表达式：{expr}", "hint": "请用 sympy 可解析写法，如 x**2, sin(x)"}

    ys = [p[1] for p in pts]
    y0, y1 = min(ys), max(ys)
    if abs(y1 - y0) < 1e-9:
        y0, y1 = y0 - 1, y1 + 1
    w, h, pad = 320, 220, 36
    ox = pad + (0 - x0) / (x1 - x0) * (w - 2 * pad) if x0 < 0 < x1 else pad
    oy = pad + (y1 - 0) / (y1 - y0) * (h - 2 * pad) if y0 < 0 < y1 else h - pad

    def map_pt(xv: float, yv: float) -> tuple[float, float]:
        px = pad + (xv - x0) / (x1 - x0) * (w - 2 * pad)
        py = pad + (y1 - yv) / (y1 - y0) * (h - 2 * pad)
        return px, py

    d = []
    for i, (xv, yv) in enumerate(pts):
        px, py = map_pt(xv, yv)
        d.append(("M" if i == 0 else "L") + f"{px:.1f},{py:.1f}")
    path = " ".join(d)
    caption = str(args.get("caption") or f"y = {expr}")
    body = _axes(ox, oy, w, h, pad) + f'<path d="{path}" fill="none" stroke="#6ec8e0" stroke-width="2"/>'
    svg = _svg_frame(w, h, body, caption)
    return {
        "ok": True,
        "kind": "plot",
        "caption": caption,
        "latex": f"y={expr}",
        "svg": svg,
        "fence": f"```jnao-svg\n{svg}\n```",
    }


def sketch_ellipse(args: dict[str, Any]) -> dict[str, Any]:
    a = float(args.get("a") or 0)
    b = float(args.get("b") or 0)
    if a <= 0 or b <= 0:
        return {"ok": False, "error": "需要正数 a、b（椭圆半轴）"}
    points = args.get("points") or []
    w, h, pad = 320, 240, 40
    scale = min((w - 2 * pad) / (2 * a), (h - 2 * pad) / (2 * b)) * 0.9
    ox, oy = w / 2, h / 2
    rx, ry = a * scale, b * scale
    caption = str(args.get("caption") or f"椭圆 x²/a² + y²/b² = 1（a={a:g}, b={b:g}）")
    body = [
        _axes(ox, oy, w, h, pad=28),
        f'<ellipse cx="{ox}" cy="{oy}" rx="{rx:.1f}" ry="{ry:.1f}" '
        f'fill="rgba(110,200,224,0.12)" stroke="#6ec8e0" stroke-width="2"/>',
    ]
    for p in points[:8]:
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            continue
        try:
            px = ox + float(p[0]) * scale
            py = oy - float(p[1]) * scale
        except (TypeError, ValueError):
            continue
        label = _esc(str(p[2]) if len(p) > 2 else f"({p[0]},{p[1]})")
        body.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#f0c674"/>')
        body.append(f'<text x="{px + 6:.1f}" y="{py - 6:.1f}" fill="#e8eef6" font-size="11">{label}</text>')
    svg = _svg_frame(w, h, "".join(body), caption)
    return {
        "ok": True,
        "kind": "ellipse",
        "caption": caption,
        "latex": rf"\frac{{x^2}}{{{a:g}^2}}+\frac{{y^2}}{{{b:g}^2}}=1",
        "svg": svg,
        "fence": f"```jnao-svg\n{svg}\n```",
    }


def sketch_points(args: dict[str, Any]) -> dict[str, Any]:
    points = args.get("points") or []
    if not points:
        return {"ok": False, "error": "需要 points，如 [[0,3,'A'],[3,1.5,'P']]"}
    xs, ys = [], []
    cleaned = []
    for p in points[:12]:
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            continue
        try:
            x, y = float(p[0]), float(p[1])
        except (TypeError, ValueError):
            continue
        xs.append(x)
        ys.append(y)
        cleaned.append((x, y, str(p[2]) if len(p) > 2 else f"({x:g},{y:g})"))
    if not cleaned:
        return {"ok": False, "error": "points 无效"}
    pad_v = 1.0
    x0, x1 = min(xs) - pad_v, max(xs) + pad_v
    y0, y1 = min(ys) - pad_v, max(ys) + pad_v
    if abs(x1 - x0) < 1e-9:
        x0, x1 = x0 - 1, x1 + 1
    if abs(y1 - y0) < 1e-9:
        y0, y1 = y0 - 1, y1 + 1
    w, h, pad = 320, 220, 36
    ox = pad + (0 - x0) / (x1 - x0) * (w - 2 * pad) if x0 < 0 < x1 else pad
    oy = pad + (y1 - 0) / (y1 - y0) * (h - 2 * pad) if y0 < 0 < y1 else h - pad
    body = [_axes(ox, oy, w, h, pad)]
    for x, y, lab in cleaned:
        px = pad + (x - x0) / (x1 - x0) * (w - 2 * pad)
        py = pad + (y1 - y) / (y1 - y0) * (h - 2 * pad)
        body.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" fill="#f0c674"/>')
        body.append(
            f'<text x="{px + 7:.1f}" y="{py - 7:.1f}" fill="#e8eef6" font-size="11">{_esc(lab)}</text>'
        )
    caption = str(args.get("caption") or "坐标系示意")
    svg = _svg_frame(w, h, "".join(body), caption)
    return {
        "ok": True,
        "kind": "points",
        "caption": caption,
        "svg": svg,
        "fence": f"```jnao-svg\n{svg}\n```",
    }


async def math_sketch(args: dict[str, Any]) -> dict[str, Any]:
    kind = str(args.get("kind") or "plot").strip().lower()
    if kind == "ellipse":
        return sketch_ellipse(args)
    if kind in ("points", "scatter", "geometry"):
        return sketch_points(args)
    return sketch_plot(args)


def register() -> None:
    register_tool(
        ToolSpec(
            name="math_sketch",
            description=(
                "【jnao-host】数学建模草图：函数曲线/椭圆/坐标系点 → SVG。"
                "几何/函数/圆锥曲线需要示意且无现成图时调用；"
                "必须把返回 JSON 的 fence 字段（```jnao-svg … ```）原样粘进回复，前端才会渲染。"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "description": "plot | ellipse | points",
                        "enum": ["plot", "ellipse", "points"],
                    },
                    "expr": {"type": "string", "description": "plot：sympy 表达式，自变量 x"},
                    "x_min": {"type": "number"},
                    "x_max": {"type": "number"},
                    "a": {"type": "number", "description": "ellipse 半长轴"},
                    "b": {"type": "number", "description": "ellipse 半短轴"},
                    "points": {
                        "type": "array",
                        "description": "[[x,y,label?], ...] 标点",
                        "items": {"type": "array"},
                    },
                    "caption": {"type": "string"},
                },
                "additionalProperties": False,
            },
            handler=math_sketch,
            permission="readonly",
            profiles=_PROFILES,
            plane="host",
            mcp_server="jnao-host",
        )
    )
