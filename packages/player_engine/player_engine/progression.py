# packages/player_engine/player_engine/progression.py
"""XP curve, level sync, and reward formulas — single source of truth (US-23)."""
from __future__ import annotations

from dataclasses import dataclass

from .config import GameConfig

L_MAX = 100
POINTS_PER_LEVEL = 3
FUSION_DAILY_LIMIT = 3
FUSION_XP_BASE = 50
FUSION_XP_LEVEL_MULT = 8
FUSION_XP_OVR_MULT = 2

MATCH_TYPE_MULT = {"friendly": 0.8, "bot": 1.0, "league": 1.25}
RESULT_BONUS = {"win": 5, "draw": 2, "loss": 0}
MATCH_XP_MIN = 1
MATCH_XP_MAX = 35

# US-24 hardening constants (mirror migration 027)
RETRO_SCALE_PCT = 75
RETRO_MAX_PER_PLAYER = 18
ALLOCATION_DAILY_CAP = 15
ALLOCATION_PACING_UNTIL = "2026-08-06"  # UTC date inclusive
MATCH_XP_DAILY_CAP = 100
DRILL_PER_PLAYER_DAILY_CAP = 5

_DEFAULT_CONFIG = GameConfig()


def xp_needed_for_level(level: int, config: GameConfig | None = None) -> int:
    """XP required to advance from level L to L+1."""
    cfg = config or _DEFAULT_CONFIG
    if level < 1 or level >= L_MAX:
        return 0
    return int(cfg.level_curve_base * (cfg.level_curve_exponent ** (level - 1)))


def cumulative_xp_for_level(level: int, config: GameConfig | None = None) -> int:
    """Total cumulative XP required to reach level (level 1 = 0 XP)."""
    if level <= 1:
        return 0
    return sum(xp_needed_for_level(i, config) for i in range(1, min(level, L_MAX)))


def level_from_xp(xp: int, l_max: int = L_MAX, config: GameConfig | None = None) -> int:
    """Derive level from total XP, capped at l_max."""
    if xp <= 0:
        return 1
    lvl = 1
    accumulated = 0
    while lvl < l_max:
        needed = xp_needed_for_level(lvl, config)
        if needed <= 0 or xp < accumulated + needed:
            break
        accumulated += needed
        lvl += 1
    return lvl


def xp_progress(xp: int, config: GameConfig | None = None) -> tuple[int, int, int]:
    """Return (current_level, xp_in_current_level, xp_needed_for_next_level)."""
    level = level_from_xp(xp, config=config)
    if level >= L_MAX:
        return level, 0, 0
    floor_xp = cumulative_xp_for_level(level, config)
    in_level = max(0, xp - floor_xp)
    needed = xp_needed_for_level(level, config)
    return level, in_level, needed


def skill_points_earned_for_level(level: int) -> int:
    return max(0, level - 1) * POINTS_PER_LEVEL


def scale_retroactive_reward(missing_raw: int) -> int:
    """Payable retro skill points: 75% scaled, capped at RETRO_MAX_PER_PLAYER."""
    if missing_raw <= 0:
        return 0
    scaled = (missing_raw * RETRO_SCALE_PCT) // 100
    return min(RETRO_MAX_PER_PLAYER, max(1, scaled))


def fusion_xp_reward(sacrifice_level: int, sacrifice_ovr: int) -> int:
    return FUSION_XP_BASE + (max(1, sacrifice_level) * FUSION_XP_LEVEL_MULT) + (max(0, sacrifice_ovr) * FUSION_XP_OVR_MULT)


def _base_match_development_xp(minutes_played: int, match_rating: float | None) -> int:
    # ponytail: mirrors training_engine.calculate_match_development_xp; keep in sync manually
    if minutes_played <= 0:
        return 0
    xp = 5 + (minutes_played // 30) * 3
    if match_rating is not None:
        xp += int(round((float(match_rating) - 6.0) * 2))
    return max(1, min(20, xp))


def match_xp_reward(
    *,
    minutes_played: int,
    match_rating: float | None,
    match_type: str = "bot",
    goals: int = 0,
    assists: int = 0,
    motm: bool = False,
    result: str = "loss",
    age: int | None = None,
) -> int:
    base = _base_match_development_xp(minutes_played, match_rating)
    if base <= 0:
        return 0
    mult = MATCH_TYPE_MULT.get(match_type, 1.0)
    bonuses = goals * 5 + assists * 3 + (15 if motm else 0) + RESULT_BONUS.get(result, 0)
    raw = max(MATCH_XP_MIN, min(MATCH_XP_MAX, int(base * mult) + bonuses))
    if age is not None:
        from .age_manager import apply_xp_age_multiplier
        return apply_xp_age_multiplier(raw, age)
    return raw


def drill_xp_reward(
    tier_xp_base: int,
    player_level: int,
    age: int | None = None,
    *,
    training_ground_level: int = 1,
) -> int:
    """Diminishing returns + optional age multiplier + training ground flat bonus."""
    lvl = max(1, player_level)
    mult = 1.0 / (1.0 + 0.05 * (lvl - 1))
    raw = max(1, int(tier_xp_base * mult))
    if age is not None:
        from .age_manager import apply_xp_age_multiplier
        raw = apply_xp_age_multiplier(raw, age)
    from economy.facility_effects import training_ground_drill_xp_bonus
    return raw + training_ground_drill_xp_bonus(training_ground_level)


@dataclass(frozen=True)
class ApplyXpResult:
    old_level: int
    new_level: int
    levels_gained: int
    skill_points_granted: int
    xp_added: int
    xp_wasted: int
    new_xp: int


def simulate_apply_card_xp(
    current_xp: int,
    xp_amount: int,
    l_max: int = L_MAX,
    config: GameConfig | None = None,
) -> ApplyXpResult:
    """Pure model of apply_card_xp RPC (for tests and UI previews)."""
    old_level = level_from_xp(current_xp, l_max=l_max, config=config)
    if old_level >= l_max or xp_amount <= 0:
        wasted = xp_amount if old_level >= l_max and xp_amount > 0 else 0
        return ApplyXpResult(
            old_level=old_level,
            new_level=old_level,
            levels_gained=0,
            skill_points_granted=0,
            xp_added=0,
            xp_wasted=wasted,
            new_xp=current_xp,
        )
    cap_xp = cumulative_xp_for_level(l_max, config)
    raw_new = current_xp + xp_amount
    new_xp = min(raw_new, cap_xp)
    xp_added = new_xp - current_xp
    xp_wasted = max(0, raw_new - cap_xp)
    new_level = level_from_xp(new_xp, l_max=l_max, config=config)
    levels_gained = new_level - old_level
    return ApplyXpResult(
        old_level=old_level,
        new_level=new_level,
        levels_gained=levels_gained,
        skill_points_granted=levels_gained * POINTS_PER_LEVEL,
        xp_added=xp_added,
        xp_wasted=xp_wasted,
        new_xp=new_xp,
    )
