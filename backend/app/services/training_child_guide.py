"""给孩子看的训练说明 — 不用技术排课文案"""

from __future__ import annotations

from app.services.content_meta import parse_item_instruction


def _block_of(item) -> str:
    meta = parse_item_instruction(
        item.instructions if item.instructions and item.instructions.strip().startswith("{") else None
    )
    return meta.get("block") or "A"


def _display_name(title: str | None) -> str:
    t = (title or "").strip()
    for suffix in ("（待同步）", "（占位）", "（感知训练）"):
        t = t.replace(suffix, "")
    return t or "这一项"


def build_coach_text_for_plan(plan, *, main_line: str | None = None) -> str:
    """根据已生成的 TrainingItem 写给孩子/家长的操作指引"""
    items = sorted(plan.items, key=lambda i: i.sort_order)
    if not items:
        return "选好时间后，点「开始训练」，按顺序听音频、做完打卡就好。"

    blocks: dict[str, list] = {}
    for it in items:
        blocks.setdefault(_block_of(it), []).append(it)

    lines = ["今天按顺序练就可以啦："]
    order = sorted(blocks.keys(), key=lambda b: (len(b), b))

    for i, block in enumerate(order, start=1):
        block_items = blocks[block]
        names = [_display_name(it.title) for it in block_items]
        if len(names) == 1:
            step = f"听「{names[0]}」"
        else:
            step = " → ".join(f"「{n}」" for n in names)
            step = f"按顺序听 {step}"
        mins = [it.duration_min for it in block_items if it.duration_min and it.duration_min > 0]
        if mins:
            step += f"（大约 {sum(mins)} 分钟）"
        lines.append(f"{i}. 训练 {block}：{step}")

    lines.append("每块练完点下面「训练打卡」，填一下练了多久。")
    if len(order) > 1:
        lines.append("训练 A 打卡完成后，才能开始训练 B。")
    lines.append("加油，认真听完全程哦！")

    return "\n".join(lines)


def is_technical_schedule_note(text: str | None) -> bool:
    if not text or not str(text).strip():
        return True
    t = str(text)
    markers = (
        "训练块",
        "(primary)",
        "(optional)",
        "块1(",
        "块 1(",
        "块2(",
        "块 2(",
        "→感知",
        "时长 ",
        "分钟 →",
        "synergy",
    )
    return any(m in t for m in markers)
