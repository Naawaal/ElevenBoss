# app/engine/training_engine.py

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TrainingWeekInput:
    player_id: str
    age: int
    overall: int
    potential: int
    sharpness: int                    # current player sharpness (0–100)
    morale: int                       # current player morale (0–100)
    current_readiness_modifier: float # current season readiness modifier (0.85–1.05)
    plan_type: str                    # "balanced"|"fitness"|"sharpness"|"tactical"
    intensity: str                    # "light"|"normal"|"heavy"
    is_injured: bool
    training_pitch_level: int         # 1–5; sourced from Facility row, default 1


@dataclass(frozen=True)
class TrainingWeekResult:
    player_id: str
    xp_earned: int
    sharpness_delta: int
    morale_delta: int
    readiness_modifier: float  # new readiness modifier to store in DB
    notes: list[str] = field(default_factory=list)


def calculate_training_week(inp: TrainingWeekInput) -> TrainingWeekResult:
    """
    Calculates the deterministic outcome of a single training week for a player.
    Does not mutate any input state. Clamps readiness between 0.85 and 1.05.
    """
    if inp.is_injured:
        return TrainingWeekResult(
            player_id=inp.player_id,
            xp_earned=0,
            sharpness_delta=0,
            morale_delta=-1,
            readiness_modifier=inp.current_readiness_modifier,
            notes=["Missed training (injured)"],
        )

    # Base values per plan
    # Plan | XP | Sharpness Δ | Morale Δ | Readiness Δ
    plan_rules = {
        "balanced":  {"xp": 8,  "sharpness": 2,  "morale": 1,  "readiness": 0.00},
        "fitness":   {"xp": 4,  "sharpness": 0,  "morale": 0,  "readiness": 0.03},
        "sharpness": {"xp": 6,  "sharpness": 5,  "morale": -1, "readiness": 0.02},
        "tactical":  {"xp": 10, "sharpness": 1,  "morale": 3,  "readiness": 0.00},
    }

    # Intensity modifiers
    # Intensity | XP Multiplier | Morale Δ | Readiness Δ
    intensity_rules = {
        "light":  {"xp_mult": 0.75, "morale": 1,  "readiness": 0.01},
        "normal": {"xp_mult": 1.00, "morale": 0,  "readiness": 0.00},
        "heavy":  {"xp_mult": 1.25, "morale": -2, "readiness": -0.02},
    }

    plan = inp.plan_type.lower() if inp.plan_type else "balanced"
    if plan not in plan_rules:
        plan = "balanced"

    intensity = inp.intensity.lower() if inp.intensity else "normal"
    if intensity not in intensity_rules:
        intensity = "normal"

    base_rule = plan_rules[plan]
    int_rule = intensity_rules[intensity]

    # XP Calculation
    xp_earned = int(base_rule["xp"] * int_rule["xp_mult"])
    
    # Facility Level Bonus: +1 XP per level above 1 (Level 1 gives +0)
    pitch_level = max(1, min(5, inp.training_pitch_level))
    facility_bonus = pitch_level - 1
    xp_earned += facility_bonus

    # Deltas
    sharpness_delta = base_rule["sharpness"]
    morale_delta = base_rule["morale"] + int_rule["morale"]

    # Readiness Modifier
    readiness_delta = base_rule["readiness"] + int_rule["readiness"]
    new_readiness = inp.current_readiness_modifier + readiness_delta
    # Clamp readiness between 0.85 and 1.05 and round to 2 decimal places
    new_readiness = max(0.85, min(1.05, new_readiness))
    new_readiness = round(new_readiness, 2)

    return TrainingWeekResult(
        player_id=inp.player_id,
        xp_earned=xp_earned,
        sharpness_delta=sharpness_delta,
        morale_delta=morale_delta,
        readiness_modifier=new_readiness,
        notes=[],
    )


def calculate_match_development_xp(
    minutes_played: int,
    match_rating: float | None,
) -> int:
    """
    Calculates XP earned from a league match appearance. Clamps between 1 and 20.
    """
    if minutes_played <= 0:
        return 0

    xp = 5
    xp += (minutes_played // 30) * 3

    if match_rating is not None:
        # round((rating - 6.0) * 2)
        rating_diff = float(match_rating) - 6.0
        xp += int(round(rating_diff * 2))

    # Clamp between 1 and 20
    return max(1, min(20, xp))


def calculate_season_training_bonus(
    *,
    age: int,                          # POST-AGING age (after age_players() and retirement checks run)
    overall: int,
    potential: int,
    training_xp: int,
    match_xp: int,
    weeks_trained: int,
    season_bonus_already_applied: bool,
) -> int:
    """
    Determines the OVR training bonus (0, 1, or 2) at the end of the season.
    Does not mutate any arguments.
    """
    if season_bonus_already_applied:
        return 0

    # Age 30+ players do not get training bonuses.
    if age >= 30:
        return 0

    # Already at or exceeding potential (safety check).
    if overall >= potential:
        return 0

    total_xp = training_xp + match_xp
    avg_weekly_xp = total_xp / max(1, weeks_trained)

    if avg_weekly_xp < 16:
        raw_bonus = 0
    elif avg_weekly_xp < 28:
        raw_bonus = 1
    else:
        raw_bonus = 2

    # Cannot exceed potential ceiling
    return min(raw_bonus, potential - overall)
