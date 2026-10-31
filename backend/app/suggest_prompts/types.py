"""提问引导 chip 类型 — 三业务共用形状，展示格式按 audience 转换。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

# report=天赋报告对话；student=孩子引导；parent=家长引导；qa=学科答疑（兼容）
SuggestAudience = Literal["report", "student", "parent", "qa"]


@dataclass(frozen=True)
class SuggestChip:
    """一条可点提问。label 展示，text 发送；{talent} 由调用方替换。"""

    label: str
    text: str
    hot: bool = False

    def rendered(self, *, talent: str = "") -> SuggestChip:
        t = (talent or "").strip() or "这份天赋"
        return SuggestChip(
            label=self.label.replace("{talent}", t),
            text=self.text.replace("{talent}", t),
            hot=self.hot,
        )

    def as_guide_item(self) -> dict[str, str]:
        return {"label": self.label, "text": self.text}

    def as_report_item(self) -> dict[str, Any]:
        return {"q": self.label or self.text, "hot": bool(self.hot)}
