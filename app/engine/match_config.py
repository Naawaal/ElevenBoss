# app/engine/match_config.py

from dataclasses import dataclass, field

@dataclass(frozen=True)
class MatchEngineConfig:
    # --- Interval Settings ---
    # 9 intervals × 10 minutes = 90 minutes per match.
    # Per-interval card rates must be kept in sync with interval_count
    # using: p_interval = 1 - (1 - p_match) ^ (1 / interval_count)
    interval_count: int = 9
    interval_length_minutes: int = 10
    fitness_decay_per_interval: float = 0.04   # 4% per interval (~36% total over 90 min)

    # --- Expected Goals (xG) ---
    base_xg: float = 1.30
    home_advantage_xg: float = 0.20
    min_xg: float = 0.20
    max_xg: float = 4.00
    randomness_factor: float = 0.22
    max_common_goals: int = 5

    # Per-interval xG clamps (scaled from full-match: min=0.20, max=4.00)
    # Formula: x_interval = x_match * (interval_length_minutes / 90)
    # At 9×10: min≈0.022, max≈0.444
    min_xg_interval: float = 0.022
    max_xg_interval: float = 0.444
    
    # --- Card Rates (per-match) ---
    yellow_card_base_rate: float = 0.18
    red_card_base_rate: float = 0.02
    direct_red_prob: float = 0.005
    gk_yellow_prob: float = 0.02
    def_dm_yellow_prob: float = 0.15
    other_yellow_prob: float = 0.08
    double_yellow_min_gap: int = 1
    double_yellow_max_gap: int = 10

    # Per-interval card rates (rescaled from per-match via: p_i = 1 - (1-p)^(1/interval_count))
    # Pre-computed at interval_count=9. Must be kept in sync when interval_count changes.
    # gk:        1 - (1-0.02)^(1/9)  ≈ 0.0022
    # def/dm:    1 - (1-0.15)^(1/9)  ≈ 0.0180
    # other:     1 - (1-0.08)^(1/9)  ≈ 0.0093
    # direct_red:1 - (1-0.005)^(1/9) ≈ 0.0006
    gk_yellow_prob_interval: float = 0.0022
    def_dm_yellow_prob_interval: float = 0.0180
    other_yellow_prob_interval: float = 0.0093
    direct_red_prob_interval: float = 0.0006

    # --- Substitutions & Injuries (Milestone B) ---
    # Fitness fraction below which a fatigue substitution may be triggered (per interval).
    # GK slots are excluded from fatigue sub consideration.
    fatigue_sub_threshold: float = 0.60

    # Maximum substitutions allowed per team per match (modern football rules: 5).
    max_substitutions: int = 5

    # Base injury probability per player per interval at full fitness (1.0).
    # Probability scales with fatigue: p = base * (1.0 + (1.0 - current_fitness))
    # So at 50% fitness: p = 0.0015 * 1.5 = 0.00225 per player per interval.
    #
    # Expected injuries/match at full fitness:
    #   interval_count × players_both_teams × p = 9 × 22 × 0.0015 ≈ 0.30
    # That gives roughly 1 injury every 3–4 matches, consistent with real football.
    # Tune upward (e.g. 0.003 → ~0.6/match) if you want injuries more frequently.
    injury_base_probability: float = 0.0015


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

    # --- Multiplier Stacking Cap ---
    # Caps the product of tactic + momentum multipliers applied to per-interval xG
    # to prevent compounding into unrealistic territory.
    max_combined_multiplier: float = 1.60

    # --- Tactics (Milestone D) ---
    # Each tactic has 5 fields: attack_mult, defense_mult, midfield_mult,
    # foul_prob_mult, fatigue_mult.  Named tactic_<name>_<field> so that
    # get_tactic_profile() can resolve them via getattr().
    #
    # BALANCED — neutral baseline
    tactic_balanced_attack_mult:    float = 1.00
    tactic_balanced_defense_mult:   float = 1.00
    tactic_balanced_midfield_mult:  float = 1.00
    tactic_balanced_foul_prob_mult: float = 1.00
    tactic_balanced_fatigue_mult:   float = 1.00

    # HIGH_PRESS — aggressive, tires quickly, fouls more
    tactic_high_press_attack_mult:    float = 1.12
    tactic_high_press_defense_mult:   float = 0.93
    tactic_high_press_midfield_mult:  float = 1.10
    tactic_high_press_foul_prob_mult: float = 1.30
    tactic_high_press_fatigue_mult:   float = 1.35   # fitness decays 35% faster

    # POSSESSION — midfield dominance, lower direct attacking output
    tactic_possession_attack_mult:    float = 0.92
    tactic_possession_defense_mult:   float = 1.05
    tactic_possession_midfield_mult:  float = 1.15
    tactic_possession_foul_prob_mult: float = 0.80
    tactic_possession_fatigue_mult:   float = 0.95

    # COUNTER_ATTACK — defensive shape, punches on the break
    tactic_counter_attack_attack_mult:    float = 0.88
    tactic_counter_attack_defense_mult:   float = 1.12
    tactic_counter_attack_midfield_mult:  float = 0.90
    tactic_counter_attack_foul_prob_mult: float = 0.90
    tactic_counter_attack_fatigue_mult:   float = 0.90

    # PARK_THE_BUS — extreme defensive, minimal attacking threat
    tactic_park_the_bus_attack_mult:    float = 0.70
    tactic_park_the_bus_defense_mult:   float = 1.25
    tactic_park_the_bus_midfield_mult:  float = 0.80
    tactic_park_the_bus_foul_prob_mult: float = 1.10
    tactic_park_the_bus_fatigue_mult:   float = 0.75   # less running = less fatigue

    # --- Momentum (Milestone E) ---
    # momentum_goal_boost:   Additional momentum score gained per goal of lead.
    # momentum_goal_cap:     Maximum goal differential used in momentum calc (caps runaway).
    # momentum_recency_boost: Extra boost if you scored in the previous interval.
    # momentum_attack_weight: How much of the momentum score maps to attack mult.
    # momentum_defense_weight: How much maps to defense mult.
    # momentum_max_mult:     Per-team per-direction multiplier ceiling (and 1/ceiling floor).
    #
    # At defaults with a 2-goal lead:
    #   base_boost = 2 × 0.05 = 0.10
    #   home_atk   = 1.0 + 0.10 × 0.70 = 1.07  (7% attack boost for leading side)
    momentum_goal_boost:     float = 0.05
    momentum_goal_cap:       int   = 3
    momentum_recency_boost:  float = 0.08   # "just scored" pulse, lasts one interval
    momentum_attack_weight:  float = 0.70
    momentum_defense_weight: float = 0.30
    momentum_max_mult:       float = 1.10
    momentum_red_card_weight: float = 1.0   # each red card vs. opponent = N-goal deficit in momentum calc

    # --- Dixon-Coles Scoreline Correlation (Milestone C) ---
    # Negative correlation corrects for under-prediction of low-scoring draws
    # (specifically 0-0 and 1-1) and over-prediction of narrow wins (1-0 and 0-1).
    dixon_coles_rho: float = -0.1

    # --- Goal Source & Player Depth (Milestone F) ---
    penalty_probability_per_match: float = 0.12
    set_piece_goal_probability: float = 0.18
    own_goal_base_probability: float = 0.008
    own_goal_deficit_multiplier: float = 0.05
    consistency_low_threshold: int = 40
    consistency_high_threshold: int = 80

    # Rating range boundaries for consistency scaling
    rating_base_min_low: float = 4.5
    rating_base_min_high: float = 6.3
    rating_base_max_low: float = 8.5
    rating_base_max_high: float = 6.8

    # Scorer weighting tables for different goal sources
    penalty_scorer_weights: dict[str, float] = field(default_factory=lambda: {
        "ST": 100.0, "CF": 100.0, "LW": 90.0, "RW": 90.0, "CAM": 80.0,
        "LM": 50.0, "RM": 50.0, "CM": 50.0, "CDM": 20.0, "DEFENDER": 10.0, "GK": 0.1
    })

    set_piece_scorer_weights: dict[str, float] = field(default_factory=lambda: {
        "CB": 100.0, "LB": 60.0, "RB": 60.0, "LWB": 60.0, "RWB": 60.0,
        "ST": 100.0, "CF": 100.0, "LW": 50.0, "RW": 50.0, "CAM": 50.0,
        "LM": 30.0, "RM": 30.0, "CM": 40.0, "CDM": 30.0, "GK": 0.1, "DEFENDER": 80.0
    })

    own_goal_scorer_weights: dict[str, float] = field(default_factory=lambda: {
        "CB": 100.0, "LB": 80.0, "RB": 80.0, "LWB": 80.0, "RWB": 80.0,
        "CDM": 40.0, "CM": 20.0, "LM": 10.0, "RM": 10.0, "CAM": 5.0,
        "ST": 2.0, "CF": 2.0, "LW": 2.0, "RW": 2.0, "GK": 5.0, "DEFENDER": 90.0
    })
