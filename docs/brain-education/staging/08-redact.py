# -*- coding: utf-8 -*-
"""步骤8 脱敏与合规：aligned -> redacted 精确替换脚本（可重复执行）"""
import json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
REDACTED = os.path.join(BASE, "redacted")

# 决策：署名=正文泛化+meta留注记；效果数字=仅保留须核实标注（不删原文）
REPLACEMENTS = [
    # ---------- ① 案例/学员实名 -> 角色代号 ----------
    ("frontline/cases.md", "| 郑××中考线 |", "| 某中考学员线 |"),
    ("frontline/cases.md", "| 甘明英孙女 |", "| 某教育工作者孙女 |"),
    ("frontline/cases.md", "| 杨子琪妈妈 |", "| 某全职陪读家长 |"),
    ("frontline/products.md", "学员连战：14 岁跟学", "某学员：14 岁跟学"),
    # ---------- ② 正文团队署名 -> 角色（meta 留原名+注记） ----------
    ("frontline/products.md",
     "- **管理团**：张总 + 核心班子，教天赋运用",
     "- **管理团**：创始人 + 核心班子，教天赋运用"),
    ("frontline/products.md",
     "- **播商学院**：殷老师、李敏智老师主抓",
     "- **播商学院**：教学负责人主抓"),
    ("frontline/sales.md", "### 张宇核心逻辑三条", "### 主讲人核心逻辑三条"),
    ("frontline/quotes.md",
     "精选自同事金句合集 / 汇总_小宇 / 大会版",
     "精选自同事金句合集 / 大会版"),
    ("README.md", "同事张宇汇总资料包", "同事汇总资料包"),
    ("README.md", "- **主讲方**：张总（张宇老师）及其团队",
     "- **主讲方**：创始人（主讲人）及其团队"),
    ("README.md", "`meta/_raw/zhangyu-pack/`", "`meta/_raw/team-pack/`"),
    # ---------- ④ 处方教学类比注记（非医疗） ----------
    ("practice/learning-methods.md",
     "**处方总则**：先定位，再分析，后指导 ≈ 诊断 → 病理 → 处方。",
     "**处方总则**：先定位，再分析，后指导 ≈ 诊断 → 病理 → 处方"
     "（**教学类比，非医疗处方**，指「定位问题 → 分析原因 → 给出指导」）。"),
    ("practice/talents-application.md",
     "> 与 [learning-methods.md](learning-methods.md) 五维分表一致；此处补「怎么学 / 怎么带」一句话，方便当场开处方。",
     "> 与 [learning-methods.md](learning-methods.md) 五维分表一致；此处补「怎么学 / 怎么带」一句话，方便当场开处方"
     "（**教学类比，非医疗处方**）。"),
    ("practice/talents-application.md",
     "4. **处方**：培养口诀 + 1～2 个训练能力 + 家长最小动作",
     "4. **处方**（教学类比，非医疗处方）：培养口诀 + 1～2 个训练能力 + 家长最小动作"),
]

# 块头固定横幅（safety 免责 + meta 溯源注记）
BANNERS = [
    ("training/safety.md",
     "<!-- /canonical-banner -->\n> 来源：《超脑进化之书》",
     "<!-- /canonical-banner -->\n"
     "<!-- compliance-banner -->\n"
     "> **免责声明（医疗/心理）**：本文为**教学与 SOP 参考**，非医疗诊断、治疗建议或处方。"
     "文中「聪明疼」「感知幻觉」「幻视幻听」等为《超脑进化之书》术语体系，用于一线识别与分流；"
     "遇身体不适、用药、心理异常，**须咨询医生或专业人士**。\n"
     "<!-- /compliance-banner -->\n"
     "> 来源：《超脑进化之书》"),
    ("meta/sources.md",
     "<!-- /canonical-banner -->\n## 来源",
     "<!-- /canonical-banner -->\n"
     "<!-- compliance-banner -->\n"
     "> **内部溯源注记（meta）**：本表为资料溯源索引，保留真实人名与归档文件名（如甘明英、杨子琪、王艳、张宇/小宇）。"
     "入库建议标记为 internal 或排除于对外检索；正文知识库已做泛化处理。原始档案「源材料未随包公开」，未随本包交付。\n"
     "<!-- /compliance-banner -->\n"
     "## 来源"),
]

def apply_all():
    results = []
    ok = True
    for rel, old, new in REPLACEMENTS + BANNERS:
        path = os.path.join(REDACTED, rel)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        n = text.count(old)
        if n == 0:
            ok = False
            results.append({"file": rel, "matched": 0, "applied": 0, "status": "NOT_FOUND"})
            print(f"[FAIL] 未命中: {rel} :: {old[:40]}...")
            continue
        # 只替换整段（所有命中都应一致）
        text = text.replace(old, new)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        results.append({"file": rel, "matched": n, "applied": n, "status": "ok"})
        print(f"[ok] {rel}: {n} 处命中并替换")
    return results, ok

if __name__ == "__main__":
    results, ok = apply_all()
    with open(os.path.join(BASE, "08-redaction-apply.json"), "w", encoding="utf-8") as f:
        json.dump({"applied": results}, f, ensure_ascii=False, indent=2)
    sys.exit(0 if ok else 1)
