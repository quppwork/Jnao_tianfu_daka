"""Fee · 多模型官价表（能力无关的纯函数价目）。

层：model_cost（Fee 横切）。调价只改本文件并升 RATE_VERSION。
单位：对外元；库内 cost_milli_cent（0.001 分）= yuan * 100_000。
DeepSeek：https://api-docs.deepseek.com/zh-cn/quick_start/pricing
（V4.1 Flash → API `deepseek-flash`；峰谷 + 缓存命中）。
百炼知识库规格费另算。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

# 调价发版时递增，写入 upstream_usage_event.rate_version
RATE_VERSION = "2026-11-ds-v41flash"

_TZ_SH = ZoneInfo("Asia/Shanghai")


def yuan_per_1m_to_milli_per_1k(yuan_per_1m: float) -> int:
    """元/百万 token → 每 1K token 的 milli-cent（0.001 分）。"""
    # 1 元 = 100 分 = 100_000 milli-cent
    # 每 1K = 1/1000 百万 → yuan_per_1m / 1000 * 100_000 = yuan_per_1m * 100
    return int(round(float(yuan_per_1m) * 100))


def milli_cent_to_yuan(milli: int) -> float:
    return max(0, int(milli or 0)) / 100_000.0


def is_deepseek_peak(at: datetime | None = None) -> bool:
    """DeepSeek 高峰：北京时间周一至周五 9–12、14–18（不含法定假日日历，假日近似按空闲）。"""
    if at is None:
        now = datetime.now(_TZ_SH)
    elif at.tzinfo is None:
        now = at.replace(tzinfo=_TZ_SH)
    else:
        now = at.astimezone(_TZ_SH)
    if now.weekday() >= 5:  # Sat/Sun
        return False
    t = now.time()
    return (time(9, 0) <= t < time(12, 0)) or (time(14, 0) <= t < time(18, 0))


@dataclass(frozen=True)
class ModelRate:
    """单模型官价（元/百万 tokens）。"""

    provider: str
    model: str
    # 输入未命中缓存
    prompt_miss_idle: float
    prompt_miss_peak: float
    # 输入命中缓存
    prompt_hit_idle: float
    prompt_hit_peak: float
    # 输出
    completion_idle: float
    completion_peak: float

    def estimate_milli(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        prompt_cache_hit_tokens: int = 0,
        peak: bool = False,
    ) -> int:
        p = max(0, int(prompt_tokens))
        c = max(0, int(completion_tokens))
        hit = min(max(0, int(prompt_cache_hit_tokens)), p)
        miss = p - hit
        if peak:
            miss_y, hit_y, out_y = (
                self.prompt_miss_peak,
                self.prompt_hit_peak,
                self.completion_peak,
            )
        else:
            miss_y, hit_y, out_y = (
                self.prompt_miss_idle,
                self.prompt_hit_idle,
                self.completion_idle,
            )
        # milli-cent = tokens/1000 * (yuan_per_1m * 100)
        miss_m = yuan_per_1m_to_milli_per_1k(miss_y)
        hit_m = yuan_per_1m_to_milli_per_1k(hit_y)
        out_m = yuan_per_1m_to_milli_per_1k(out_y)
        return (miss * miss_m + hit * hit_m + c * out_m) // 1000


@dataclass
class RateCard:
    rates: list[ModelRate]
    default: ModelRate
    version: str = RATE_VERSION

    def resolve(self, provider: str, model: str | None = None) -> ModelRate:
        prov = (provider or "").strip().lower()
        mod = _normalize_model(prov, model)
        for row in self.rates:
            if row.provider == prov and row.model == mod:
                return row
        for row in self.rates:
            if row.provider == prov and row.model == "*":
                return row
        return self.default


def _normalize_model(provider: str, model: str | None) -> str:
    mod = (model or "").strip().lower()
    if provider in ("deepseek", "doubao"):
        # V4.1 Flash 官方 API 名；旧 flash / vision-exp 名均按 flash 计费
        if mod in (
            "",
            "*",
            "default",
            "fast",
            "flash",
            "deepseek-flash",
            "deepseek-v4-flash",
            "deepseek-v4-flash-vision-exp",
            "deepseek-chat",
            "deepseek-reasoner",
        ):
            return "deepseek-flash"
        if mod in ("deepseek-v4-pro", "pro", "slow"):
            return "deepseek-v4-pro"
        return mod
    return mod or "*"


def default_rate_card() -> RateCard:
    """DeepSeek 官价 + 其它厂商占位；按具体 model id 解析。"""
    flash = ModelRate(
        provider="deepseek",
        model="deepseek-flash",
        prompt_miss_idle=1.0,
        prompt_miss_peak=2.0,
        prompt_hit_idle=0.02,
        prompt_hit_peak=0.04,
        completion_idle=4.0,
        completion_peak=8.0,
    )
    pro = ModelRate(
        provider="deepseek",
        model="deepseek-v4-pro",
        prompt_miss_idle=4.5,
        prompt_miss_peak=9.0,
        prompt_hit_idle=0.15,
        prompt_hit_peak=0.30,
        completion_idle=13.5,
        completion_peak=27.0,
    )
    # 百炼对话粗估（知识库规格费另说）；未细化到具体 qwen 型号前用通配
    bl = ModelRate(
        provider="bailian",
        model="*",
        prompt_miss_idle=0.8,
        prompt_miss_peak=0.8,
        prompt_hit_idle=0.8,
        prompt_hit_peak=0.8,
        completion_idle=2.0,
        completion_peak=2.0,
    )
    ds_star = ModelRate(
        provider="deepseek",
        model="*",
        prompt_miss_idle=flash.prompt_miss_idle,
        prompt_miss_peak=flash.prompt_miss_peak,
        prompt_hit_idle=flash.prompt_hit_idle,
        prompt_hit_peak=flash.prompt_hit_peak,
        completion_idle=flash.completion_idle,
        completion_peak=flash.completion_peak,
    )
    return RateCard(
        version=RATE_VERSION,
        rates=[
            flash,
            pro,
            ds_star,
            bl,
            ModelRate(
                provider="dashscope",
                model="*",
                prompt_miss_idle=bl.prompt_miss_idle,
                prompt_miss_peak=bl.prompt_miss_peak,
                prompt_hit_idle=bl.prompt_hit_idle,
                prompt_hit_peak=bl.prompt_hit_peak,
                completion_idle=bl.completion_idle,
                completion_peak=bl.completion_peak,
            ),
        ],
        default=flash,
    )


def estimate_usage_cost(
    *,
    provider: str,
    model: str | None,
    prompt_tokens: int,
    completion_tokens: int,
    prompt_cache_hit_tokens: int = 0,
    at: datetime | None = None,
) -> tuple[int, str]:
    """返回 (cost_milli_cent, rate_version)。按官网价 × 峰谷 × 缓存命中。"""
    card = default_rate_card()
    rate = card.resolve(provider, model)
    peak = False
    if (provider or "").strip().lower() in ("deepseek", "doubao"):
        peak = is_deepseek_peak(at)
    return rate.estimate_milli(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        prompt_cache_hit_tokens=prompt_cache_hit_tokens,
        peak=peak,
    ), card.version
