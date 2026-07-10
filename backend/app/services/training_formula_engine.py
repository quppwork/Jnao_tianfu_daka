"""v3.0 公式引擎 — Decision Tree + Strategy Pipeline

架构：
  Layer 1: Decision Tree — 根据上下文选择策略
  Layer 2: Strategy Pipeline — 策略 = Phase 序列，Phase 间通过 PlanContext 传递

用法:
    from app.services.training_formula_engine import expand_formula
    result = expand_formula(120, overall_tier=3, grade_band="junior",
                            skill_tiers={"影像追忆": 3, "扫描速记": 1, ...})
    # → {"slots": [...], "strategy": "weight_with_bundle", ...}
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date

from config.loader import load_training_curriculum


# ═══════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════

SKILL_CODE: dict[str, str] = {
    "超脑阅读": "A", "影像追忆": "B", "扫描速记": "C",
    "极速运算": "D", "极速学习": "E", "文科奥秘": "F",
    "理科奥秘": "G", "天赋绘画": "H", "音乐灵感": "I",
}

CODE_SKILL: dict[str, str] = {v: k for k, v in SKILL_CODE.items()}

ELECTIVE_SKILLS: frozenset[str] = frozenset({"多元感知", "精力恢复", "高效作业"})


# ═══════════════════════════════════════════════════════════════
# 数据类
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class HistoryEntry:
    """单日训练摘要，供 Decision Tree 条件判断"""
    plan_date: date
    planned_minutes: int
    skills: tuple[str, ...]


@dataclass(frozen=True)
class PlanContext:
    """排课上下文 — 在 Phase 之间传递的不可变状态"""
    # ── 输入 ──
    planned_minutes: int
    tier: int                              # overall_tier
    grade_band: str                        # primary_low / primary_high / junior / senior
    available_skills: tuple[str, ...] = ()
    skill_tiers: Mapping[str, int] = field(
        default_factory=dict
    )
    history: tuple[HistoryEntry, ...] = ()

    # ── Phase 产出 ──
    total_slots: int = 0
    bundle_id: str | None = None
    bundle_skills: tuple[str, ...] = ()
    slots_used_by_bundle: int = 0
    bundle_note: str = ""
    weights: Mapping[str, float] = field(default_factory=dict)
    decay_map: Mapping[str, float] = field(default_factory=dict)
    selected: tuple[str, ...] = ()
    grade_notes: tuple[dict, ...] = ()
    elective_tags: tuple[dict, ...] = ()
    exam_note: str | None = None
    homework_skill: str = ""
    homework_count: int = 0

    def evolve(self, **kwargs) -> "PlanContext":
        return replace(self, **kwargs)


@dataclass(frozen=True)
class Strategy:
    """策略 = 命名 Phase 序列"""
    name: str
    phases: tuple[Callable[[PlanContext, dict], PlanContext], ...]
    description: str


# ═══════════════════════════════════════════════════════════════
# 谓词库（Decision Tree 条件节点）
# ═══════════════════════════════════════════════════════════════

def _predicate_consecutive_days_short(ctx: PlanContext, params: dict) -> bool:
    """用户是否连续 N 天选择 ≤max_minutes 的短时训练"""
    min_days = params.get("min_days", 7)
    max_minutes = params.get("max_minutes", 20)
    if len(ctx.history) < min_days:
        return False
    recent = ctx.history[-min_days:]
    return all(h.planned_minutes <= max_minutes for h in recent)


def _predicate_tier_in(ctx: PlanContext, params: dict) -> bool:
    """当前整体 Tier 是否在指定集合中"""
    return ctx.tier in params.get("tiers", [])


def _predicate_grade_in(ctx: PlanContext, params: dict) -> bool:
    """当前学段是否在指定集合中"""
    return ctx.grade_band in params.get("grades", [])


def _predicate_duration_range(ctx: PlanContext, params: dict) -> bool:
    """时长是否在 [min, max] 区间"""
    lo = params.get("min", 0)
    hi = params.get("max", 9999)
    return lo <= ctx.planned_minutes <= hi


def _predicate_always(ctx: PlanContext, params: dict) -> bool:
    return True


PREDICATES: dict[str, Callable[[PlanContext, dict], bool]] = {
    "consecutive_days_short": _predicate_consecutive_days_short,
    "tier_in": _predicate_tier_in,
    "grade_in": _predicate_grade_in,
    "duration_range": _predicate_duration_range,
    "always": _predicate_always,
}


# ═══════════════════════════════════════════════════════════════
# Decision Tree
# ═══════════════════════════════════════════════════════════════

def resolve_strategy(
    node_id: str,
    nodes: dict,
    ctx: PlanContext,
    predicates: dict,
) -> tuple[str, dict]:
    """沿决策树走到策略叶子，返回 (strategy_name, params)"""
    node = nodes[node_id]
    if node["type"] == "strategy":
        return node["strategy"], node.get("params", {})

    # 条件节点
    check = predicates[node["predicate"]]
    passed = check(ctx, node.get("params", {}))
    next_node = node["on_true"] if passed else node["on_false"]
    return resolve_strategy(next_node, nodes, ctx, predicates)


# ═══════════════════════════════════════════════════════════════
# Phase 函数
# ═══════════════════════════════════════════════════════════════

# ── 槽位工具 ──

def _lookup_slot_entry(slot_table: list[dict],
                       planned_minutes: int) -> dict:
    """§3 槽位表: 返回匹配的完整条目（含 homework / exam_note）"""
    for entry in slot_table:
        mins = entry["minutes"]
        if isinstance(mins, int) and planned_minutes == mins:
            return entry
        if isinstance(mins, list) and len(mins) == 2:
            if mins[0] <= planned_minutes <= mins[1]:
                return entry

    # fallback
    first = slot_table[0]
    first_min = first["minutes"]
    lo = first_min if isinstance(first_min, int) else first_min[0]
    if planned_minutes < lo:
        return first
    return slot_table[-1]


# ── Phase 1: 槽位解析 ──

def resolve_slots(ctx: PlanContext, cfg: dict) -> PlanContext:
    assert ctx.planned_minutes >= 5, "训练时长至少 5 分钟"
    entry = _lookup_slot_entry(cfg["slot_table"], ctx.planned_minutes)

    # 高效作业/极速学习（上级要求：≥2h 追加，≥3阶替换）
    homework_cfg = entry.get("homework", {})
    tier_hw = homework_cfg.get(f"tier_{ctx.tier}") if homework_cfg else None
    hw_skill = tier_hw.get("skill", "") if tier_hw else ""
    hw_count = tier_hw.get("count", 0) if tier_hw else 0

    return ctx.evolve(
        total_slots=entry["slots"],
        exam_note=entry.get("exam_note"),
        homework_skill=hw_skill,
        homework_count=hw_count,
    )


# ── Phase: 最小分钟数覆写（forced_upgrade 策略首步）──

def override_min_minutes(ctx: PlanContext, params: dict) -> PlanContext:
    floor = params.get("min_minutes", 0)
    if ctx.planned_minutes < floor:
        return ctx.evolve(planned_minutes=floor)
    return ctx


# ── 捆绑选择（按个体技能 Tier）──

def _select_bundle(bundles: list[dict], ctx: PlanContext) -> dict:
    """
    选捆绑：搭档技能个体 Tier 最低的优先（需要更多练习）。
    同 Tier 按技能编码字母序 A > B > C > D > E。
    选修技能不参与比较。
    """
    def _key(bundle: dict) -> tuple[int, str]:
        tiers: list[int] = []
        codes: list[str] = []
        for s in bundle["skills"]:
            if s in ELECTIVE_SKILLS:
                continue
            tiers.append(ctx.skill_tiers.get(s, 99))
            codes.append(SKILL_CODE.get(s, "Z"))
        min_tier = min(tiers) if tiers else 99
        first_code = min(codes) if codes else "Z"
        return (min_tier, first_code)

    return min(bundles, key=_key)


def _build_decay_map(tier: int, cfg: dict) -> dict[str, float]:
    """构建 skill_code → decay_factor 映射"""
    decay_rules = cfg.get("decay_rules", {})
    key_skills = decay_rules.get("key_skills", {})
    secondary = decay_rules.get("secondary_skills", {})
    key_set = set(key_skills.get(f"tier_{tier}", []))
    secondary_set = set(secondary.get(f"tier_{tier}", []))
    factors = decay_rules.get("factors", {})
    key_factor = factors.get("key", 0.7)
    secondary_factor = factors.get("secondary", 0.5)

    result: dict[str, float] = {}
    for code in key_set:
        result[code] = key_factor
    for code in secondary_set:
        result[code] = secondary_factor
    return result


# ── Phase 2: 捆绑选择 ──

def require_bundle(ctx: PlanContext, cfg: dict) -> PlanContext:
    """匹配捆绑 → 消耗槽位 → 预衰减权重"""
    bundles_cfg = cfg.get("bundles", {})
    tier_bundles: list[dict] = bundles_cfg.get(f"tier_{ctx.tier}", [])
    if not tier_bundles:
        return ctx  # no-op

    # 过滤：槽数不足 + min_total_slots 不满足
    feasible: list[dict] = []
    for b in tier_bundles:
        if b["cost_slots"] > ctx.total_slots:
            continue
        min_slots = b.get("min_total_slots", 0)
        if min_slots > ctx.total_slots:
            continue
        feasible.append(b)

    if not feasible:
        return ctx

    bundle = _select_bundle(feasible, ctx)

    # 加载权重
    tier_key = f"tier_{ctx.tier}"
    weights: dict[str, float] = dict(cfg["tier_weights"].get(tier_key, {}))
    decay_map = _build_decay_map(ctx.tier, cfg)

    # 预衰减：捆绑中出现的必修技能
    for skill in bundle["skills"]:
        code = SKILL_CODE.get(skill, "")
        if code in weights and skill not in ELECTIVE_SKILLS:
            d = decay_map.get(code, 0.7)
            weights[code] = round(weights[code] * d, 6)

    # 初高中标记
    bundle_note = ""
    grade_note_map = bundle.get("grade_note", {})
    if ctx.grade_band in grade_note_map:
        bundle_note = grade_note_map[ctx.grade_band]

    return ctx.evolve(
        bundle_id=bundle["id"],
        bundle_skills=tuple(bundle["skills"]),
        slots_used_by_bundle=bundle["cost_slots"],
        weights=weights,
        decay_map=decay_map,
        bundle_note=bundle_note,
    )


# ── Phase 3a: 权重贪心填充 ──

def greedy_fill(ctx: PlanContext, cfg: dict) -> PlanContext:
    """贪心 max(w) → 衰减 → 重复，填满剩余槽位"""
    remaining = ctx.total_slots - ctx.slots_used_by_bundle
    if remaining <= 0:
        return ctx

    # 权重初始化（若 require_bundle 未执行则在这里加载）
    weights = dict(ctx.weights) if ctx.weights else dict(
        cfg["tier_weights"].get(f"tier_{ctx.tier}", {})
    )
    decay_map = dict(ctx.decay_map) if ctx.decay_map else _build_decay_map(
        ctx.tier, cfg
    )
    threshold = float(cfg.get("decay_rules", {}).get("threshold", 0.01))

    selected: list[str] = []
    for _ in range(remaining):
        candidates = {k: v for k, v in weights.items() if v >= threshold}
        if not candidates:
            break
        best = max(candidates, key=candidates.get)
        selected.append(best)
        d = decay_map.get(best, 0.7)
        weights[best] = round(weights[best] * d, 6)

    return ctx.evolve(
        weights=weights,
        decay_map=decay_map,
        selected=tuple(selected),
    )


# ── Phase 3b: 轮换填充（diversity_round_robin 策略）──

def round_robin_fill(ctx: PlanContext, cfg: dict) -> PlanContext:
    """权重系统下线，技能按固定轮序排列"""
    remaining = ctx.total_slots - ctx.slots_used_by_bundle
    if remaining <= 0:
        return ctx

    tier_key = f"tier_{ctx.tier}"
    order_cfg = cfg.get("tier_skills_order", {})
    ordered: list[str] = list(order_cfg.get(tier_key, ctx.available_skills))
    if not ordered:
        ordered = list(ctx.available_skills)

    # 上次出现过的技能排到末尾
    if ctx.history:
        last_codes = set()
        for skill_name in ctx.history[-1].skills:
            code = SKILL_CODE.get(skill_name, "")
            if code:
                last_codes.add(code)
        ordered = [c for c in ordered if c not in last_codes] + \
                  [c for c in ordered if c in last_codes]

    selected: list[str] = []
    for i in range(remaining):
        skill = ordered[i % len(ordered)]
        selected.append(skill)

    return ctx.evolve(selected=tuple(selected))


# ── Phase 4: 学段标注 ──

def annotate_grades(ctx: PlanContext, cfg: dict) -> PlanContext:
    """初高中特定技能标记「不推荐」"""
    notes_cfg: dict = cfg.get("grade_notes", {})
    band_notes: list[dict] = notes_cfg.get(ctx.grade_band, [])
    if not band_notes:
        return ctx

    all_codes = set(ctx.bundle_skills) | set(ctx.selected)
    notes: list[dict] = []
    for entry in band_notes:
        skill_name = entry["skill"]
        code = SKILL_CODE.get(skill_name, skill_name)
        if code in all_codes:
            notes.append({
                "skill": skill_name,
                "mark": entry.get("mark", "不推荐"),
                "reason": entry.get("reason", ""),
            })

    return ctx.evolve(grade_notes=tuple(notes))


# ── Phase 5: 选修标记 ──

def tag_electives(ctx: PlanContext, cfg: dict) -> PlanContext:
    """识别选修技能，附加 blocks_next / has_checkin 标记"""
    elective_rules: dict = cfg.get("elective_rules", {})
    tags: list[dict] = []
    for code in (*ctx.bundle_skills, *ctx.selected):
        skill_name = CODE_SKILL.get(code, code)  # 尝试映射回中文名
        if skill_name in elective_rules:
            er = elective_rules[skill_name]
        elif code in elective_rules:
            er = elective_rules[code]
        else:
            continue
        tags.append({
            "skill": skill_name if skill_name in elective_rules else code,
            "has_checkin": er.get("has_checkin", False),
            "blocks_next": er.get("blocks_next", True),
        })

    return ctx.evolve(elective_tags=tuple(tags))


# ═══════════════════════════════════════════════════════════════
# Strategy Registry
# ═══════════════════════════════════════════════════════════════

def _make_strategy(name: str, description: str, *phases) -> Strategy:
    return Strategy(name=name, phases=phases, description=description)


STRATEGIES: dict[str, Strategy] = {
    "weight_based": _make_strategy(
        "weight_based",
        "标准权重贪心排课（Tier 1/2/4/5/6+ 默认）",
        resolve_slots,
        greedy_fill,
        annotate_grades,
        tag_electives,
    ),
    "weight_with_bundle": _make_strategy(
        "weight_with_bundle",
        "捆绑 + 权重贪心补位（Tier 3）",
        resolve_slots,
        require_bundle,
        greedy_fill,
        annotate_grades,
        tag_electives,
    ),
    "diversity_round_robin": _make_strategy(
        "diversity_round_robin",
        "轮换排课（连续 7 天短时）",
        resolve_slots,
        round_robin_fill,
        annotate_grades,
        tag_electives,
    ),
    "forced_upgrade": _make_strategy(
        "forced_upgrade",
        "强制升级时长 + 捆绑排课（连续 14 天短时）",
        override_min_minutes,
        resolve_slots,
        require_bundle,
        greedy_fill,
        annotate_grades,
        tag_electives,
    ),
}


# ═══════════════════════════════════════════════════════════════
# 结果构建
# ═══════════════════════════════════════════════════════════════

def _ctx_to_result(ctx: PlanContext, strategy_name: str,
                   reason: str | None, cfg: dict) -> dict:
    """PlanContext → API 响应格式"""
    # 合并技能列表：捆绑 + 补位
    all_codes = list(ctx.bundle_skills) + list(ctx.selected)

    # 上级要求：≥2h 追加高效作业/极速学习（≥3阶替换）
    for _ in range(ctx.homework_count):
        if ctx.homework_skill:
            all_codes.append(ctx.homework_skill)

    # ≥480min 追加精力恢复
    if ctx.planned_minutes >= 480:
        all_codes.append("精力恢复")

    # 映射为中文名
    slot_mapping: dict = cfg.get("slot_mapping", {})
    resolved: list[str] = []
    for code in all_codes:
        resolved.append(slot_mapping.get(code, CODE_SKILL.get(code, code)))

    # 构建 elective_notes（保持向后兼容的格式）
    elective_rules: dict = cfg.get("elective_rules", {})
    elective_notes: list[dict] = []
    for skill_name in resolved:
        if skill_name in elective_rules:
            er = elective_rules[skill_name]
            elective_notes.append({
                "skill": skill_name,
                "has_checkin": er.get("has_checkin", False),
                "blocks_next": er.get("blocks_next", True),
            })

    # 初高中 C 标注（向后兼容 c_note）
    c_note = None
    for gn in ctx.grade_notes:
        if gn.get("skill") == "扫描速记":
            c_note = gn.get("mark")

    result: dict = {
        "slots": resolved,
        "elective_notes": elective_notes,
        "c_note": c_note,
        "exam_note": ctx.exam_note,
        "minutes": ctx.planned_minutes,
        # ── v3.0 新增字段 ──
        "strategy": strategy_name,
        "bundle_id": ctx.bundle_id,
        "bundle_note": ctx.bundle_note,
        "grade_notes": list(ctx.grade_notes),
    }
    if reason:
        result["reason"] = reason
    return result


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def expand_formula(
    planned_minutes: int,
    overall_tier: int = 1,
    grade_band: str = "primary_low",
    *,
    skill_tiers: dict[str, int] | None = None,
    history: tuple[HistoryEntry, ...] = (),
) -> dict:
    """将训练时长展开为技能组合列表。

    Args:
        planned_minutes: 用户选择的训练时长（分钟）
        overall_tier: 整体 Tier = min(各技能个体 Tier)
        grade_band: 学段（primary_low / primary_high / junior / senior）
        skill_tiers: 每个技能的个体 Tier {"影像追忆": 3, "扫描速记": 1, ...}
        history: 近 N 天训练记录（用于连续短时检测等条件判断）

    Returns:
        {
            "slots": ["超脑阅读", "影像追忆", ...],
            "elective_notes": [...],
            "c_note": None | "不建议",
            "exam_note": None | str,
            "minutes": int,
            "strategy": "weight_based",      # v3.0 新增
            "bundle_id": "B3",               # v3.0 新增（仅捆绑策略）
            "bundle_note": "不推荐",          # v3.0 新增
            "grade_notes": [...],            # v3.0 新增
            "reason": "连续 7 天...",         # v3.0 新增（仅特殊策略）
        }
    """
    cfg = load_training_curriculum()
    if not cfg:
        return {
            "slots": [], "elective_notes": [], "c_note": None,
            "exam_note": None, "minutes": planned_minutes,
        }

    tier_key = f"tier_{overall_tier}"
    ctx = PlanContext(
        planned_minutes=planned_minutes,
        tier=overall_tier,
        grade_band=grade_band,
        available_skills=tuple(cfg.get("tier_skills", {}).get(tier_key, [])),
        skill_tiers=skill_tiers or {},
        history=history,
    )

    # Layer 1: Decision Tree → (策略名, 参数)
    tree = cfg.get("decision_tree", {})
    strategy_name = "weight_based"
    params: dict = {}
    if tree and tree.get("root"):
        strategy_name, params = resolve_strategy(
            tree["root"], tree.get("nodes", {}), ctx, PREDICATES
        )

    # 参数覆写
    reason: str | None = params.get("reason")
    if "min_minutes" in params:
        min_min = int(params["min_minutes"])
        if ctx.planned_minutes < min_min:
            ctx = ctx.evolve(planned_minutes=min_min)

    # Layer 2: Strategy → Phase Pipeline
    strategy = STRATEGIES.get(strategy_name, STRATEGIES["weight_based"])
    merged_cfg = {**cfg, **params}
    for phase in strategy.phases:
        ctx = phase(ctx, merged_cfg)

    return _ctx_to_result(ctx, strategy_name, reason, cfg)


# ═══════════════════════════════════════════════════════════════
# 向后兼容
# ═══════════════════════════════════════════════════════════════

_GRADE_BANDS = ("primary_low", "primary_high", "junior", "senior")


def max_formula_item_count(planned_minutes: int) -> int:
    """时长对应的最大训练项数（跨 tier/学段取保守上界）。"""
    n = 0
    for tier in (1, 3, 5):
        for band in _GRADE_BANDS:
            result = expand_formula(
                planned_minutes, overall_tier=tier, grade_band=band
            )
            n = max(n, len(result.get("slots") or []))
    return n


def duration_slot(planned_minutes: int) -> dict:
    """时长档位元数据（向后兼容）。"""
    items = max_formula_item_count(planned_minutes)
    return {"items": items, "minutes": planned_minutes}
