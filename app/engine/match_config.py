# app/engine/match_config.py

from dataclasses import dataclass, field

@dataclass(frozen=True)
class MatchEngineConfig:
    # --- Expected Goals (xG) ---
    base_xg: float = 1.30
    home_advantage_xg: float = 0.20
    min_xg: float = 0.20
    max_xg: float = 4.00
    randomness_factor: float = 0.22
    max_common_goals: int = 5
    
    # --- Card Rates ---
    yellow_card_base_rate: float = 0.18
    red_card_base_rate: float = 0.02
    direct_red_prob: float = 0.005
    gk_yellow_prob: float = 0.02
    def_dm_yellow_prob: float = 0.15
    other_yellow_prob: float = 0.08
    double_yellow_min_gap: int = 1
    double_yellow_max_gap: int = 10

    # --- Match Stats ---
    possession_delta_multiplier: float = 0.4
    min_possession: int = 35
    max_possession: int = 65
    
    base_shots_min: int = 6
    base_shots_max: int = 18
    shots_strength_multiplier: float = 0.2
    min_shots: int = 3
    max_shots: int = 30
    
    sot_ratio_min: float = 0.25
    sot_ratio_max: float = 0.55

    # --- Scorer & Assist Priority Weights ---
    scorer_weights: dict[str, float] = field(default_factory=lambda: {
        "ST": 100.0,
        "CF": 100.0,
        "LW": 80.0,
        "RW": 80.0,
        "CAM": 60.0,
        "LM": 30.0,
        "RM": 30.0,
        "CM": 30.0,
        "LDM": 15.0,
        "RDM": 15.0,
        "CDM": 15.0,
        "GK": 0.01,
        "DEFENDER": 5.0
    })
    
    assist_probability: float = 0.70
    assist_weights: dict[str, float] = field(default_factory=lambda: {
        "CAM": 100.0,
        "LM": 100.0,
        "RM": 100.0,
        "CM": 100.0,
        "LDM": 100.0,
        "RDM": 100.0,
        "CDM": 100.0,
        "ST": 60.0,
        "CF": 60.0,
        "LW": 60.0,
        "RW": 60.0,
        "GK": 1.0,
        "DEFENDER": 30.0
    })

    # --- Team Strength Modifiers ---
    gk_slots: frozenset[str] = field(default_factory=lambda: frozenset({"GK"}))
    defense_slots: frozenset[str] = field(default_factory=lambda: frozenset({"LB", "CB1", "CB2", "CB3", "RB", "LWB", "RWB"}))
    midfield_slots: frozenset[str] = field(default_factory=lambda: frozenset({"LM", "CM1", "CM2", "CM3", "RM", "LDM", "RDM", "CAM"}))
    attack_slots: frozenset[str] = field(default_factory=lambda: frozenset({"LW", "ST", "RW", "ST1", "ST2"}))
    
    suitability_natural: float = 1.0
    suitability_compatible: float = 0.85
    suitability_out_of_position: float = 0.6
    suitability_gk_swap: float = 0.2
    
    min_fitness_factor: float = 0.1
    home_strength_boost: float = 1.05

    # --- Match Ratings ---
    rating_base_min: float = 6.0
    rating_base_max: float = 7.0
    rating_scorer_bonus: float = 1.5
    rating_assist_bonus: float = 0.8
    rating_clean_sheet_bonus: float = 1.0
    rating_conceded_penalty: float = 0.25
    rating_yellow_card_penalty: float = 0.5
    rating_red_card_penalty: float = 1.5
    rating_win_bonus: float = 0.5
    rating_draw_bonus: float = 0.1
    rating_loss_penalty: float = 0.5
    rating_clamp_min: float = 4.0
    rating_clamp_max: float = 10.0
