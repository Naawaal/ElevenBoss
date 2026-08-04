# packages/economy/economy/facility_effects.py
"""Club facility upgrade costs and gameplay effects (Phase C / 051 YA V2)."""

from __future__ import annotations

from dataclasses import dataclass

FACILITY_UPGRADE_COSTS: tuple[int, ...] = (750, 2000, 5000, 12000)
HOSPITAL_UPGRADE_COSTS: tuple[int, ...] = (1500, 4000, 10000, 25000, 60000)
FACILITY_MAX_LEVEL: int = 5
HOSPITAL_MAX_LEVEL: int = 5
FACILITY_WEEKLY_CAP_DAYS: int = 7

# Target level -> minimum career matches required before upgrading TO that level
FACILITY_MIN_MATCHES: dict[int, int] = {2: 5, 4: 20}
HOSPITAL_MIN_MATCHES: dict[int, int] = {2: 5, 4: 20}


@dataclass(frozen=True)
class YouthAcademyTier:
    """Legacy OVR/POT windows (015). V2 generation uses rarity weights instead."""

    level: int
    pot_min: int
    pot_max: int
    ovr_min: int
    ovr_max: int
    gem_chance: float


YOUTH_ACADEMY_TIERS: dict[int, YouthAcademyTier] = {
    1: YouthAcademyTier(1, 72, 82, 50, 65, 0.0),
    2: YouthAcademyTier(2, 72, 85, 52, 66, 0.05),
    3: YouthAcademyTier(3, 72, 88, 54, 67, 0.10),
    4: YouthAcademyTier(4, 72, 91, 55, 68, 0.15),
    5: YouthAcademyTier(5, 72, 94, 56, 69, 0.20),
}

# Spec 051 — academy holding slots by YA level
ACADEMY_SLOT_CAPS: dict[int, int] = {1: 3, 2: 3, 3: 4, 4: 4, 5: 5}

# Spec 051 — rarity weights by YA level (Legendary only at L5)
YOUTH_RARITY_WEIGHTS: dict[int, dict[str, float]] = {
    1: {"Common": 0.85, "Rare": 0.15, "Epic": 0.0, "Legendary": 0.0},
    2: {"Common": 0.70, "Rare": 0.25, "Epic": 0.05, "Legendary": 0.0},
    3: {"Common": 0.55, "Rare": 0.35, "Epic": 0.10, "Legendary": 0.0},
    4: {"Common": 0.40, "Rare": 0.40, "Epic": 0.20, "Legendary": 0.0},
    5: {"Common": 0.30, "Rare": 0.40, "Epic": 0.299, "Legendary": 0.001},
}

# Starting OVR band by YA level (clamped under rolled POT)
YOUTH_OVR_BANDS: dict[int, tuple[int, int]] = {
    1: (50, 58),
    2: (52, 60),
    3: (54, 62),
    4: (55, 64),
    5: (56, 65),
}

# POT generation band inside rarity ceiling (inclusive)
YOUTH_POT_BANDS: dict[str, tuple[int, int]] = {
    "Common": (60, 75),
    "Rare": (70, 85),
    "Epic": (80, 92),
    "Legendary": (88, 99),
}

# Initial visible POT range width (051 scout fog)
ACADEMY_INITIAL_RANGE_WIDTH: dict[int, int] = {1: 12, 2: 10, 3: 8, 4: 6, 5: 5}

# Advisory ready OVR by YA level (early promote still allowed)
ACADEMY_READY_OVR_BY_LEVEL: dict[int, int] = {1: 62, 2: 63, 3: 65, 4: 66, 5: 68}

# Spec 015 — paid scout tiers (mirrors game_config defaults)
SCOUT_TIER_COSTS: dict[str, int] = {"quick": 3000, "standard": 10000, "deep": 25000}
SCOUT_TIER_HOURS: dict[str, int] = {"quick": 2, "standard": 8, "deep": 24}

LEGENDARY_DEFAULT_ENABLED: bool = True


def academy_slot_cap(academy_level: int) -> int:
    """Max academy seats for YA level (clamped 1–5)."""
    level = max(1, min(FACILITY_MAX_LEVEL, int(academy_level)))
    return ACADEMY_SLOT_CAPS[level]


def scout_tier_cost(tier: str) -> int | None:
    return SCOUT_TIER_COSTS.get(tier)


def scout_tier_hours(tier: str) -> int | None:
    return SCOUT_TIER_HOURS.get(tier)


def facility_upgrade_cost(current_level: int) -> int | None:
    """Coin cost to upgrade YA/TG from current_level to current_level + 1."""
    if current_level < 1 or current_level >= FACILITY_MAX_LEVEL:
        return None
    return FACILITY_UPGRADE_COSTS[current_level - 1]


def hospital_upgrade_cost(current_level: int) -> int | None:
    """Coin cost to upgrade Hospital from current_level (0–4) to next."""
    if current_level < 0 or current_level >= HOSPITAL_MAX_LEVEL:
        return None
    return HOSPITAL_UPGRADE_COSTS[current_level]


def hospital_bed_capacity(hospital_level: int) -> int:
    return max(0, int(hospital_level)) + 1


def hospital_recovery_multiplier(hospital_level: int) -> float:
    return 1.0 / (1.0 + 0.2 * max(0, int(hospital_level)))


def training_ground_drill_xp_bonus(training_ground_level: int) -> int:
    """Flat drill XP bonus: L1 +0 … L5 +4."""
    level = max(1, min(FACILITY_MAX_LEVEL, training_ground_level))
    return level - 1


def youth_academy_tier(academy_level: int) -> YouthAcademyTier:
    level = max(1, min(FACILITY_MAX_LEVEL, academy_level))
    return YOUTH_ACADEMY_TIERS[level]


def youth_rarity_weights(
    academy_level: int,
    *,
    legendary_enabled: bool = LEGENDARY_DEFAULT_ENABLED,
) -> dict[str, float]:
    """Normalized rarity weights for V2 academy generation."""
    level = max(1, min(FACILITY_MAX_LEVEL, int(academy_level)))
    raw = dict(YOUTH_RARITY_WEIGHTS[level])
    if not legendary_enabled or level < 5:
        raw["Legendary"] = 0.0
    total = sum(raw.values())
    if total <= 0:
        return {"Common": 1.0, "Rare": 0.0, "Epic": 0.0, "Legendary": 0.0}
    return {k: v / total for k, v in raw.items()}


def youth_ovr_band(academy_level: int) -> tuple[int, int]:
    level = max(1, min(FACILITY_MAX_LEVEL, int(academy_level)))
    return YOUTH_OVR_BANDS[level]


def youth_pot_band(rarity: str) -> tuple[int, int]:
    if rarity not in YOUTH_POT_BANDS:
        raise ValueError(f"Unsupported rarity: {rarity!r}")
    return YOUTH_POT_BANDS[rarity]


def academy_ready_ovr(academy_level: int) -> int:
    level = max(1, min(FACILITY_MAX_LEVEL, int(academy_level)))
    return ACADEMY_READY_OVR_BY_LEVEL[level]


def academy_initial_range_width(academy_level: int) -> int:
    level = max(1, min(FACILITY_MAX_LEVEL, int(academy_level)))
    return ACADEMY_INITIAL_RANGE_WIDTH[level]


def academy_growth_speed_label(academy_level: int) -> str:
    """Relative development speed for facility preview copy."""
    level = max(1, min(FACILITY_MAX_LEVEL, int(academy_level)))
    # Mirrors academy_daily_points base term 10 + 5*level (+ pot/25 variable)
    pts = 10 + 5 * level
    return f"~{pts}+ pts/day"


def validate_youth_rarity_weights(weights: dict[str, float]) -> None:
    """FR-021: non-negative weights; reject empty total."""
    if any(v < 0 for v in weights.values()):
        raise ValueError("Rarity weights must be non-negative")
    if sum(weights.values()) <= 0:
        raise ValueError("Rarity weights must sum to a positive total")


def youth_facility_preview(current_level: int) -> dict[str, object] | None:
    """Before→after effects for upgrading YA from current_level → next."""
    if current_level < 1 or current_level >= FACILITY_MAX_LEVEL:
        return None
    nxt = current_level + 1
    w_cur = youth_rarity_weights(current_level)
    w_nxt = youth_rarity_weights(nxt)
    return {
        "from_level": current_level,
        "to_level": nxt,
        "capacity": (academy_slot_cap(current_level), academy_slot_cap(nxt)),
        "range_width": (
            academy_initial_range_width(current_level),
            academy_initial_range_width(nxt),
        ),
        "growth": (
            academy_growth_speed_label(current_level),
            academy_growth_speed_label(nxt),
        ),
        "rarity_odds": {
            "from": {k: round(v * 100, 2) for k, v in w_cur.items()},
            "to": {k: round(v * 100, 2) for k, v in w_nxt.items()},
        },
        "ready_ovr": (academy_ready_ovr(current_level), academy_ready_ovr(nxt)),
    }


def min_matches_for_next_level(
    current_level: int, facility_key: str = "youth_academy"
) -> int:
    """Matches required to upgrade to current_level + 1 (0 if none)."""
    table = HOSPITAL_MIN_MATCHES if facility_key == "hospital" else FACILITY_MIN_MATCHES
    return table.get(current_level + 1, 0)


def facility_label(facility_key: str) -> str:
    return {
        "youth_academy": "Youth Academy",
        "training_ground": "Training Ground",
        "hospital": "Hospital",
    }.get(facility_key, facility_key)
