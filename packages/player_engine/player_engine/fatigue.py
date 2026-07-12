# packages/player_engine/player_engine/fatigue.py
"""Per-card fatigue drain, recovery, and match stat penalties (US fatigue Phase 1 + 009)."""
from __future__ import annotations

from typing import Literal

# Defaults mirror game_config (056_recovery_qol_balance.sql)
FATIGUE_BASE_DRAIN = 18
FATIGUE_PASSIVE_BASE = 25
FATIGUE_PASSIVE_TG_PER_LEVEL = 5
# Deprecated flat alias: equals TG level 1 passive (25 + 5*1 = 30)
FATIGUE_PASSIVE_PER_DAY = FATIGUE_PASSIVE_BASE + FATIGUE_PASSIVE_TG_PER_LEVEL
FATIGUE_HOSPITAL_PER_DAY = 45
FATIGUE_BENCH_PER_MATCH = 25
FATIGUE_RECOVERY_SESSION = 40
FATIGUE_MIN = 0
FATIGUE_MAX = 100

TacticStance = Literal["attack", "defend", "neutral"]

# Phase-attr multipliers by fatigue band (GDD table). Keys match MatchPlayerCard attrs.
_PENALTY_TIERS: list[tuple[int, int, dict[str, float]]] = [
    # (lo, hi_inclusive, multipliers as 1.0 + delta)
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
        return 8
    if stance == "defend":
        return -4
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
    intensity: bool = False,
    base_drain: int = FATIGUE_BASE_DRAIN,
) -> int:
    """
    Drain = Base - (PHY * 0.15) + tactic + intensity.
    Example: PHY 70, Attack, intensity → round(18 - 10.5 + 8 + 5) = 21.
    """
    raw = base_drain - (phy * 0.15) + tactic_modifier(stance) + (5 if intensity else 0)
    # Half-up so GDD example 24.5 → 25 (avoid banker's round)
    return max(0, int(raw + 0.5) if raw >= 0 else int(raw - 0.5))


def apply_starter_drain(current: int, drain: int) -> int:
    return clamp_fatigue(current - drain)


def apply_bench_rest(current: int, amount: int = FATIGUE_BENCH_PER_MATCH) -> int:
    return clamp_fatigue(current + amount)


def passive_recovery_amount(tg_level: int) -> int:
    """Non-hospital daily passive: base 25 + (TG level × 5). Schema TG is 1–5."""
    return max(0, FATIGUE_PASSIVE_BASE + max(int(tg_level), 0) * FATIGUE_PASSIVE_TG_PER_LEVEL)


def apply_passive_recovery(
    current: int,
    *,
    in_hospital: bool = False,
    tg_level: int = 1,
) -> int:
    if in_hospital:
        bump = FATIGUE_HOSPITAL_PER_DAY
    else:
        bump = passive_recovery_amount(tg_level)
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
