# packages/player_engine/player_engine/fatigue.py
"""Per-card fatigue drain, recovery, and match stat penalties (016 tier intensity)."""
from __future__ import annotations

from typing import Literal

from .intensity import clamp_intensity_tier

# Ops/docs mirrors; live drain uses tier bases below (not a single global base).
FATIGUE_BASE_DRAIN = 8  # Tier 1 default; prefer TIER_DRAIN_BASE
FATIGUE_PASSIVE_BASE = 35  # Tier 1 default; prefer TIER_PASSIVE_BASE
FATIGUE_PASSIVE_TG_PER_LEVEL = 2
# Deprecated flat alias (Tier 1 @ TG1): 35 + 2 = 37 — prefer passive_recovery_amount
FATIGUE_PASSIVE_PER_DAY = FATIGUE_PASSIVE_BASE + FATIGUE_PASSIVE_TG_PER_LEVEL
FATIGUE_HOSPITAL_PER_DAY = 45
FATIGUE_BENCH_PER_MATCH = 25
FATIGUE_RECOVERY_SESSION = 40
FATIGUE_MIN = 0
FATIGUE_MAX = 100

TIER_DRAIN_BASE: dict[int, int] = {1: 8, 2: 12, 3: 16}
TIER_PASSIVE_BASE: dict[int, int] = {1: 35, 2: 25, 3: 15}

TacticStance = Literal["attack", "defend", "neutral"]

# Phase-attr multipliers by fatigue band (GDD table). Keys match MatchPlayerCard attrs.
_PENALTY_TIERS: list[tuple[int, int, dict[str, float]]] = [
    (75, 100, {"pac": 1.0, "dri": 1.0, "pas": 1.0, "def_stat": 1.0, "sho": 1.0, "phy": 1.0, "overall": 1.0}),
    (50, 74, {"pac": 0.92, "dri": 0.95, "pas": 0.97, "def_stat": 1.0, "sho": 0.97, "phy": 1.0, "overall": 1.0}),
    (25, 49, {"pac": 0.80, "dri": 0.85, "pas": 0.90, "def_stat": 0.95, "sho": 0.90, "phy": 1.0, "overall": 1.0}),
    (1, 24, {"pac": 0.55, "dri": 0.70, "pas": 0.80, "def_stat": 0.85, "sho": 0.75, "phy": 1.0, "overall": 1.0}),
    (0, 0, {"pac": 0.40, "dri": 0.60, "pas": 0.70, "def_stat": 0.75, "sho": 0.65, "phy": 1.0, "overall": 1.0}),
]


def clamp_fatigue(value: int | float) -> int:
    return max(FATIGUE_MIN, min(FATIGUE_MAX, int(round(value))))


def tactic_modifier(stance: TacticStance) -> int:
    if stance == "attack":
        return 4
    if stance == "defend":
        return -2
    return 0


def stance_from_tactics_modifier(home_tactics_modifier: float) -> TacticStance:
    """Map MatchState.home_tactics_modifier (1.3 / 1.0 / 0.7) to stance."""
    if home_tactics_modifier >= 1.15:
        return "attack"
    if home_tactics_modifier <= 0.85:
        return "defend"
    return "neutral"


def match_fatigue_drain(
    phy: int,
    *,
    stance: TacticStance = "neutral",
    intensity_tier: int = 1,
) -> int:
    """
    Drain = (tier_base - PHY * 0.10) + tactic_mod.
    Example: Tier 1, PHY 70, Neutral → round(8 - 7 + 0) = 1.
    """
    base = TIER_DRAIN_BASE[clamp_intensity_tier(intensity_tier)]
    raw = base - (phy * 0.10) + tactic_modifier(stance)
    return max(0, int(raw + 0.5) if raw >= 0 else int(raw - 0.5))


def apply_starter_drain(current: int, drain: int) -> int:
    return clamp_fatigue(current - drain)


def apply_bench_rest(current: int, amount: int = FATIGUE_BENCH_PER_MATCH) -> int:
    return clamp_fatigue(current + amount)


def passive_recovery_amount(tg_level: int, *, intensity_tier: int = 1) -> int:
    """Non-hospital daily passive: tier_base + (TG level × 2)."""
    base = TIER_PASSIVE_BASE[clamp_intensity_tier(intensity_tier)]
    return max(0, base + max(int(tg_level), 0) * FATIGUE_PASSIVE_TG_PER_LEVEL)


def apply_passive_recovery(
    current: int,
    *,
    in_hospital: bool = False,
    tg_level: int = 1,
    intensity_tier: int = 1,
) -> int:
    if in_hospital:
        bump = FATIGUE_HOSPITAL_PER_DAY
    else:
        bump = passive_recovery_amount(tg_level, intensity_tier=intensity_tier)
    return clamp_fatigue(current + bump)


def apply_recovery_session(
    current: int,
    amount: int = FATIGUE_RECOVERY_SESSION,
) -> int:
    return clamp_fatigue(current + amount)


def fatigue_stat_multiplier(fatigue: int, stat_key: str) -> float:
    """Multiplier applied to phase attribute before 70/30 blend."""
    f = clamp_fatigue(fatigue)
    key = "def_stat" if stat_key in ("def", "def_stat") else stat_key
    for lo, hi, table in _PENALTY_TIERS:
        if lo <= f <= hi:
            return table.get(key, 1.0)
    return 1.0


def fatigue_indicator(fatigue: int) -> str:
    f = clamp_fatigue(fatigue)
    if f >= 75:
        return "🟢"
    if f >= 50:
        return "🟡"
    if f >= 25:
        return "🪫"
    return "🔴"


def fatigue_bar(fatigue: int, width: int = 10) -> str:
    f = clamp_fatigue(fatigue)
    filled = int(round(width * f / 100))
    return f"{fatigue_indicator(f)} Fatigue: `{'█' * filled}{'░' * (width - filled)}` **{f}%**"


def count_heavily_fatigued(starters: list[dict], *, threshold: int = 30) -> int:
    """Starters with fatigue < threshold (pre-match warning)."""
    n = 0
    for c in starters:
        if int(c.get("fatigue", 100)) < threshold:
            n += 1
    return n
