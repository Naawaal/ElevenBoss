# app/engine/match_engine.py

import math
import random
from dataclasses import dataclass, field
from app.engine.match_config import MatchEngineConfig
from app.engine.team_strength import calculate_team_strength, TeamStrength


@dataclass(frozen=True)
class MatchPlayerInput:
    player_id: str
    name: str
    position: str
    slot: str
    overall: int
    potential: int
    fitness: int
    morale: int | None = None
    consistency: int = 70
    is_goalkeeper: bool = False


@dataclass(frozen=True)
class MatchTeamInput:
    club_id: str
    club_name: str
    formation: str
    players: list[MatchPlayerInput]
    is_home: bool = False
    bench: list[MatchPlayerInput] = field(default_factory=list)
    """
    Optional bench players for substitution support (Milestone B).
    Defaults to [] so all existing callers continue to work unchanged.
    Simulations without bench entries run without substitution capability.
    """


@dataclass(frozen=True)
class MatchSimulationInput:
    fixture_id: str
    week: int
    home_team: MatchTeamInput
    away_team: MatchTeamInput
    seed: int
    home_tactic: str = "balanced"  # TacticType value; str avoids circular import at module level
    away_tactic: str = "balanced"  # Defaults to BALANCED — zero behaviour change for existing callers


@dataclass(frozen=True)
class MatchGoalEvent:
    minute: int
    club_id: str
    scorer_id: str
    assist_id: str | None
    description: str
    goal_source: str = "open_play"


@dataclass(frozen=True)
class MatchCardEvent:
    minute: int
    club_id: str
    player_id: str
    card_type: str  # "yellow" or "red"
    description: str


@dataclass(frozen=True)
class MatchSubstitutionEvent:
    minute: int
    club_id: str
    player_out_id: str
    player_in_id: str
    reason: str  # "fatigue" | "injury"
    description: str


@dataclass(frozen=True)
class MatchInjuryEvent:
    minute: int
    club_id: str
    player_id: str
    description: str


@dataclass(frozen=True)
class MatchSimulationResult:
    home_goals: int
    away_goals: int
    home_possession: int
    away_possession: int
    home_shots: int
    away_shots: int
    home_shots_on_target: int
    away_shots_on_target: int
    goals: list[MatchGoalEvent] = field(default_factory=list)
    cards: list[MatchCardEvent] = field(default_factory=list)
    substitutions: list[MatchSubstitutionEvent] = field(default_factory=list)
    injuries: list[MatchInjuryEvent] = field(default_factory=list)
    motm_player_id: str | None = None
    player_ratings: dict[str, float] = field(default_factory=dict)
    timeline_events: list = field(default_factory=list)


def _poisson_sample(rng: random.Random, L: float) -> int:
    """Standard Poisson sampler using a local Random generator."""
    if L <= 0:
        return 0
    k = 0
    p = 1.0
    limit = math.exp(-L)
    while p > limit:
        k += 1
        p *= rng.random()
    return k - 1


def _compute_tau(h: int, a: int, mu_h: float, mu_a: float, rho: float) -> float:
    """
    Calculate the Dixon-Coles score correction multiplier (tau) for a given scoreline.
    Returns 1.0 for all scores except (0,0), (1,0), (0,1), and (1,1).
    All calculated multipliers are clamped to be non-negative.
    """
    if h == 0 and a == 0:
        return max(0.0, 1.0 - rho * mu_h * mu_a)
    elif h == 1 and a == 0:
        return max(0.0, 1.0 + rho * mu_a)
    elif h == 0 and a == 1:
        return max(0.0, 1.0 + rho * mu_h)
    elif h == 1 and a == 1:
        return max(0.0, 1.0 - rho)
    else:
        return 1.0


def _compute_dc_normalization(mu_h: float, mu_a: float, rho: float) -> float:
    """
    Compute the normalization constant M (maximum tau across all outcomes)
    required for rejection sampling.
    """
    tau_00 = _compute_tau(0, 0, mu_h, mu_a, rho)
    tau_10 = _compute_tau(1, 0, mu_h, mu_a, rho)
    tau_01 = _compute_tau(0, 1, mu_h, mu_a, rho)
    tau_11 = _compute_tau(1, 1, mu_h, mu_a, rho)
    return max(1.0, tau_00, tau_10, tau_01, tau_11)


def _compute_prematch_xg(
    offense_str: TeamStrength,
    defense_str: TeamStrength,
    config: MatchEngineConfig,
    is_home: bool,
    tactic_attack_mult: float,
    tactic_defense_mult: float,
    tactic_midfield_mult: float,
) -> float:
    """
    Compute pre-match expected goals for one team.
    This corresponds to xg_full without any interval scaling or momentum multipliers.
    """
    max_c = config.max_combined_multiplier
    min_c = 1.0 / max_c

    combined_atk = max(min_c, min(max_c, tactic_attack_mult))
    combined_def = max(min_c, min(max_c, tactic_defense_mult))
    combined_mid = max(min_c, min(max_c, tactic_midfield_mult))

    effective_attack  = offense_str.attack  * combined_atk
    effective_defense = defense_str.defense * combined_def
    effective_mid_off = offense_str.midfield * combined_mid
    effective_mid_def = defense_str.midfield * combined_mid

    home_bonus = config.home_advantage_xg if is_home else 0.0
    xg_full = (
        config.base_xg
        + (effective_attack  - effective_defense)  * 0.05
        + (effective_mid_off - effective_mid_def)  * 0.03
        + home_bonus
    )
    return max(config.min_xg, min(config.max_xg, xg_full))


def _compute_interval_xg(
    offense_str: TeamStrength,
    defense_str: TeamStrength,
    fraction: float,
    config: MatchEngineConfig,
    is_home: bool,
    tactic_attack_mult: float = 1.0,
    tactic_defense_mult: float = 1.0,
    tactic_midfield_mult: float = 1.0,
    momentum_attack_mult: float = 1.0,
    momentum_defense_mult: float = 1.0,
) -> float:
    """
    Compute expected goals for one team for a single interval.

    Multiplier stacking order (Milestone D+E):
      base_xg_formula uses strength values that already embed fitness and suitability
      (computed inside calculate_team_strength). Tactic and momentum multipliers are
      then applied to the raw strength components before the xG formula runs, allowing
      them to shift both attack and defensive ratings independently.

    Stacking cap: the combined product of tactic_attack_mult and momentum_attack_mult
    is clamped to [1/max_combined, max_combined] before being applied, preventing
    HIGH_PRESS + strong momentum from compounding into unrealistic territory.

    Design note: cards are rolled at the END of each interval (after goals are sampled).
    This means a red card at minute 21 doesn't reduce team strength until interval 4
    (minutes 31-40) — a lag of up to interval_length_minutes. This is an accepted
    approximation; shorter intervals reduce the lag if needed.
    """
    max_c = config.max_combined_multiplier
    min_c = 1.0 / max_c

    # Clamp combined tactic+momentum attack multiplier
    combined_atk = max(min_c, min(max_c, tactic_attack_mult * momentum_attack_mult))
    combined_def = max(min_c, min(max_c, tactic_defense_mult * momentum_defense_mult))
    combined_mid = max(min_c, min(max_c, tactic_midfield_mult))
    # Note: momentum has no separate midfield term this year, so only tactic_midfield_mult
    # feeds this component. It is still clamped to [1/max_c, max_c] to satisfy the
    # AGENTS.md safety net ("cap... to prevent runaway compounding") for all three
    # strength components, not just attack and defense.

    effective_attack  = offense_str.attack  * combined_atk
    effective_defense = defense_str.defense * combined_def
    effective_mid_off = offense_str.midfield * combined_mid
    effective_mid_def = defense_str.midfield * combined_mid

    home_bonus = config.home_advantage_xg if is_home else 0.0
    xg_full = (
        config.base_xg
        + (effective_attack  - effective_defense)  * 0.05
        + (effective_mid_off - effective_mid_def)  * 0.03
        + home_bonus
    )
    xg_interval = xg_full * fraction
    return max(config.min_xg_interval, min(config.max_xg_interval, xg_interval))


def _roll_and_apply_cards(
    rng: random.Random,
    state,
    home_team: MatchTeamInput,
    away_team: MatchTeamInput,
    interval_start: int,
    interval_end: int,
    config: MatchEngineConfig,
    home_foul_mult: float = 1.0,
    away_foul_mult: float = 1.0,
) -> None:
    """
    Thin wrapper: calls the pure roll_cards_for_interval() for both teams, appends
    events to state.events, and removes red-carded players from state.home_active_xi /
    state.away_active_xi. All mutation is centralised here so the loop stays clean.

    home_foul_mult / away_foul_mult: tactic foul_prob_mult values (Milestone D).
    Passed through to roll_cards_for_interval() to scale per-interval yellow rates.
    """
    from app.engine.match_event_generator import roll_cards_for_interval

    for team, active_xi_attr, red_attr, foul_mult in (
        (home_team, "home_active_xi", "home_red_cards", home_foul_mult),
        (away_team, "away_active_xi", "away_red_cards", away_foul_mult),
    ):
        active_xi = getattr(state, active_xi_attr)
        new_cards = roll_cards_for_interval(
            rng, team, active_xi, interval_start, interval_end, config, foul_mult=foul_mult
        )
        state.events.extend(new_cards)

        # Apply red card removals: remove player from active XI for subsequent intervals
        red_ids = {c.player_id for c in new_cards if c.card_type == "red"}
        if red_ids:
            setattr(state, active_xi_attr, [p for p in active_xi if p.player_id not in red_ids])
            setattr(state, red_attr, getattr(state, red_attr) + len(red_ids))


def _roll_and_apply_injuries_and_subs(
    rng: random.Random,
    state,
    input_data: MatchSimulationInput,
    interval_start: int,
    interval_end: int,
    config: MatchEngineConfig,
) -> None:
    """
    Roll injuries for both teams then attempt substitutions (injury-forced first,
    then fatigue-driven). All events are appended to state.events.

    Injury order of operations per player:
      1. Injury roll fires → player fitness drops to 0.0 → added to injured_player_ids
      2. Forced sub attempted; if bench is empty or subs exhausted, player stays on
      3. After all injuries are processed, fatigue subs run (one per team if threshold hit)

    Design: injuries are always processed before fatigue subs so that a team that
    exhausts its sub allowance on an injury cannot also make a fatigue sub that interval.
    """
    from app.engine.injury_service import roll_injuries_for_interval
    from app.engine.substitution_service import try_fatigue_sub, force_injury_sub

    injury_tuples = roll_injuries_for_interval(
        rng,
        home_active_xi=state.home_active_xi,
        away_active_xi=state.away_active_xi,
        home_club_id=input_data.home_team.club_id,
        away_club_id=input_data.away_team.club_id,
        fitness=state.fitness,
        injured_player_ids=state.injured_player_ids,
        interval_start=interval_start,
        interval_end=interval_end,
        config=config,
    )

    for team_side, club_id, player, minute in injury_tuples:
        # Mark as injured and drop fitness to 0 so strength calcs reflect incapacitation
        state.injured_player_ids.add(player.player_id)
        state.fitness[player.player_id] = 0.0

        desc = f"{player.name} ({input_data.home_team.club_name if team_side == 'home' else input_data.away_team.club_name}) picks up an injury and may need to be replaced."
        state.events.append(MatchInjuryEvent(
            minute=minute,
            club_id=club_id,
            player_id=player.player_id,
            description=desc,
        ))

        # Attempt a forced substitution for the injured player
        team = input_data.home_team if team_side == "home" else input_data.away_team
        sub_event = force_injury_sub(rng, state, team_side, team, player, minute, config)
        if sub_event:
            state.events.append(sub_event)

    # Fatigue substitutions — one attempt per team per interval
    for team_side, team in (("home", input_data.home_team), ("away", input_data.away_team)):
        sub_event = try_fatigue_sub(rng, state, team_side, team, interval_start, interval_end, config)
        if sub_event:
            state.events.append(sub_event)


def _decay_fitness_selective(
    state,
    home_decay: float,
    away_decay: float,
    home_active_xi: list,
    away_active_xi: list,
) -> None:
    """
    Apply per-team fitness decay this interval.

    Home players (currently in home_active_xi) decay at home_decay rate;
    away players decay at away_decay rate. This allows HIGH_PRESS tactics to
    burn through fitness faster without affecting the opposing team.

    Players already removed from the active XI (red card, sub, injury) are not
    decayed further, which is accurate — they're no longer exerting effort.
    """
    home_ids = {p.player_id for p in home_active_xi}
    away_ids = {p.player_id for p in away_active_xi}
    for pid in state.fitness:
        if pid in home_ids:
            state.fitness[pid] = max(0.0, state.fitness[pid] - home_decay)
        elif pid in away_ids:
            state.fitness[pid] = max(0.0, state.fitness[pid] - away_decay)
        # Players no longer on the field get no further decay


def _finalize_result(
    state,
    input_data: MatchSimulationInput,
    config: MatchEngineConfig,
    rng: random.Random,
) -> MatchSimulationResult:
    """
    Reconstruct final MatchSimulationResult from accumulated state.

    Possession and shots are computed from final-interval strength values —
    these reflect end-of-match dominance after fitness decay and red cards
    have played out, which is a reasonable proxy for how the match felt.
    A per-interval weighted average would be more accurate but adds complexity
    without changing the external interface.
    """
    from app.engine.match_event_generator import generate_goal_events, generate_card_events, build_timeline
    from app.engine.match_rating import calculate_player_ratings, select_motm

    home_goals = state.home_score
    away_goals = state.away_score

    # Separate event types from the accumulated event log
    goals_list = [e for e in state.events if isinstance(e, MatchGoalEvent)]
    cards_list = [e for e in state.events if isinstance(e, MatchCardEvent)]
    subs_list  = [e for e in state.events if isinstance(e, MatchSubstitutionEvent)]
    inj_list   = [e for e in state.events if isinstance(e, MatchInjuryEvent)]

    # Possession and shots are computed from match-wide averages of the per-interval
    # strength deltas captured during the loop. This means a red card at minute 85
    # only affects 1/9th of the possession total rather than overwriting the entire
    # match stat with the weakest interval's snapshot.
    n = len(state.home_midfield_deltas) or 1   # guard against empty (should always be interval_count)
    avg_mid_delta      = sum(state.home_midfield_deltas) / n
    avg_home_att_delta = sum(state.home_attack_deltas)   / n
    avg_away_att_delta = sum(state.away_attack_deltas)   / n

    # Possession based on match-averaged midfield delta
    pos_delta = avg_mid_delta * config.possession_delta_multiplier
    home_possession = int(50 + pos_delta)
    home_possession = max(config.min_possession, min(config.max_possession, home_possession))
    away_possession = 100 - home_possession

    # Shots based on match-averaged attack vs defense delta
    home_shots = int(
        rng.randint(config.base_shots_min, config.base_shots_max)
        + avg_home_att_delta * config.shots_strength_multiplier
    )
    away_shots = int(
        rng.randint(config.base_shots_min, config.base_shots_max)
        + avg_away_att_delta * config.shots_strength_multiplier
    )
    home_shots = max(config.min_shots, min(config.max_shots, home_shots))
    away_shots = max(config.min_shots, min(config.max_shots, away_shots))

    # Shots on target
    home_sot = int(home_shots * rng.uniform(config.sot_ratio_min, config.sot_ratio_max))
    away_sot = int(away_shots * rng.uniform(config.sot_ratio_min, config.sot_ratio_max))

    # Logical safeguards: shots_on_target >= goals, shots >= shots_on_target
    home_sot = max(home_sot, home_goals)
    home_shots = max(home_shots, home_sot)
    away_sot = max(away_sot, away_goals)
    away_shots = max(away_shots, away_sot)

    # Build timeline from accumulated events
    timeline = build_timeline(
        input_data.home_team,
        input_data.away_team,
        home_goals,
        away_goals,
        goals_list,
        cards_list,
        substitutions=subs_list,
        injuries=inj_list,
    )

    # Player ratings — uses the full original rosters (not just final XI) for fairness
    player_ratings = calculate_player_ratings(
        rng,
        input_data.home_team,
        input_data.away_team,
        home_goals,
        away_goals,
        goals_list,
        cards_list,
        config,
    )

    # MOTM selection
    home_won = home_goals > away_goals
    away_won = away_goals > home_goals
    motm_player_id = select_motm(
        rng,
        input_data.home_team,
        input_data.away_team,
        player_ratings,
        home_won,
        away_won,
    )

    return MatchSimulationResult(
        home_goals=home_goals,
        away_goals=away_goals,
        home_possession=home_possession,
        away_possession=away_possession,
        home_shots=home_shots,
        away_shots=away_shots,
        home_shots_on_target=home_sot,
        away_shots_on_target=away_sot,
        goals=goals_list,
        cards=cards_list,
        substitutions=subs_list,
        injuries=inj_list,
        motm_player_id=motm_player_id,
        player_ratings=player_ratings,
        timeline_events=timeline,
    )


def simulate_match(
    input_data: MatchSimulationInput,
    config: MatchEngineConfig | None = None,
) -> MatchSimulationResult:
    """
    Simulate a match between home and away teams deterministically using a local RNG,
    with Dixon-Coles scoreline correlation applied via rejection sampling.

    Each simulation attempt runs an interval-based loop (default: 9 × 10 minutes):
      1. Recompute team strengths from the CURRENT active XI and current fitness.
      2. Sample per-interval xG and score goals (attributing scorer/assist immediately).
      3. Roll for cards at interval end; apply red card removals for subsequent intervals.
      4. Decay fitness.
    """
    if config is None:
        config = MatchEngineConfig()

    from app.engine.match_state import MatchState
    from app.engine.match_event_generator import attribute_goal
    from app.engine.tactics import TacticType, get_tactic_profile
    from app.engine.momentum import compute_momentum

    # Compute pre-match strengths and xGs to determine Dixon-Coles parameters (mu_h and mu_a)
    initial_home_str = calculate_team_strength(
        input_data.home_team.formation,
        input_data.home_team.players,
        is_home=True,
        config=config,
    )
    initial_away_str = calculate_team_strength(
        input_data.away_team.formation,
        input_data.away_team.players,
        is_home=False,
        config=config,
    )

    home_tactic = TacticType(input_data.home_tactic)
    away_tactic = TacticType(input_data.away_tactic)
    home_profile = get_tactic_profile(home_tactic, config)
    away_profile = get_tactic_profile(away_tactic, config)

    mu_h = _compute_prematch_xg(
        initial_home_str,
        initial_away_str,
        config,
        is_home=True,
        tactic_attack_mult=home_profile.attack_mult,
        tactic_defense_mult=away_profile.defense_mult,
        tactic_midfield_mult=home_profile.midfield_mult,
    )
    mu_a = _compute_prematch_xg(
        initial_away_str,
        initial_home_str,
        config,
        is_home=False,
        tactic_attack_mult=away_profile.attack_mult,
        tactic_defense_mult=home_profile.defense_mult,
        tactic_midfield_mult=away_profile.midfield_mult,
    )

    M = _compute_dc_normalization(mu_h, mu_a, config.dixon_coles_rho)

    MAX_DC_ATTEMPTS = 15
    ATTEMPT_SEED_STRIDE = 1_000_003
    last_result = None

    for attempt in range(MAX_DC_ATTEMPTS):
        # Derive a fresh seed for each attempt (pure function of original seed + attempt)
        run_seed = (input_data.seed ^ (attempt * ATTEMPT_SEED_STRIDE)) & 0xFFFF_FFFF

        rng = random.Random(run_seed)
        state = MatchState.initial(input_data)

        for i in range(config.interval_count):
            interval_start = i * config.interval_length_minutes + 1
            interval_end = (i + 1) * config.interval_length_minutes
            fraction = config.interval_length_minutes / 90.0

            # Momentum: computed at interval START from current scoreline and recent goals
            momentum = compute_momentum(state, i, config, home_club_id=input_data.home_team.club_id)

            # Recompute strength from CURRENT active XI with current fitness
            home_str = calculate_team_strength(
                input_data.home_team.formation,
                state.home_active_xi,
                is_home=True,
                config=config,
                fitness_override=state.fitness,
            )
            away_str = calculate_team_strength(
                input_data.away_team.formation,
                state.away_active_xi,
                is_home=False,
                config=config,
                fitness_override=state.fitness,
            )

            # Per-interval xG — tactic and momentum multipliers applied here
            # Stacking order: base_strength × tactic_mult × momentum_mult → clamp
            # home attacks against away defense:
            home_xg_i = _compute_interval_xg(
                home_str, away_str, fraction, config, is_home=True,
                tactic_attack_mult=home_profile.attack_mult,
                tactic_defense_mult=away_profile.defense_mult,
                tactic_midfield_mult=home_profile.midfield_mult,
                momentum_attack_mult=momentum.home_attack_mult,
                momentum_defense_mult=momentum.away_defense_mult,
            )
            # away attacks against home defense:
            away_xg_i = _compute_interval_xg(
                away_str, home_str, fraction, config, is_home=False,
                tactic_attack_mult=away_profile.attack_mult,
                tactic_defense_mult=home_profile.defense_mult,
                tactic_midfield_mult=away_profile.midfield_mult,
                momentum_attack_mult=momentum.away_attack_mult,
                momentum_defense_mult=momentum.home_defense_mult,
            )

            # Accumulate strength deltas for possession/shots rollup in _finalize_result().
            # Recorded at interval start (before card rolls) so every interval contributes
            # its pre-event strength snapshot to the match-wide average.
            state.home_midfield_deltas.append(home_str.midfield - away_str.midfield)
            state.home_attack_deltas.append(home_str.attack - away_str.defense)
            state.away_attack_deltas.append(away_str.attack - home_str.defense)

            # Sample and attribute goals for this interval
            home_goals_i = _poisson_sample(rng, home_xg_i)
            for _ in range(home_goals_i):
                minute = rng.randint(interval_start, interval_end)
                # Build a temporary MatchTeamInput reflecting current active XI
                home_view = MatchTeamInput(
                    club_id=input_data.home_team.club_id,
                    club_name=input_data.home_team.club_name,
                    formation=input_data.home_team.formation,
                    players=state.home_active_xi,
                    is_home=True,
                )
                away_view = MatchTeamInput(
                    club_id=input_data.away_team.club_id,
                    club_name=input_data.away_team.club_name,
                    formation=input_data.away_team.formation,
                    players=state.away_active_xi,
                    is_home=False,
                )
                state.events.append(attribute_goal(rng, home_view, away_view, minute, config))
                state.home_score += 1

            away_goals_i = _poisson_sample(rng, away_xg_i)
            for _ in range(away_goals_i):
                minute = rng.randint(interval_start, interval_end)
                home_view = MatchTeamInput(
                    club_id=input_data.home_team.club_id,
                    club_name=input_data.home_team.club_name,
                    formation=input_data.home_team.formation,
                    players=state.home_active_xi,
                    is_home=True,
                )
                away_view = MatchTeamInput(
                    club_id=input_data.away_team.club_id,
                    club_name=input_data.away_team.club_name,
                    formation=input_data.away_team.formation,
                    players=state.away_active_xi,
                    is_home=False,
                )
                state.events.append(attribute_goal(rng, away_view, home_view, minute, config))
                state.away_score += 1

            # Roll cards at END of interval — tactic foul_prob_mult scales yellow rates
            _roll_and_apply_cards(
                rng, state,
                input_data.home_team,
                input_data.away_team,
                interval_start, interval_end,
                config,
                home_foul_mult=home_profile.foul_prob_mult,
                away_foul_mult=away_profile.foul_prob_mult,
            )

            # Injuries and substitutions: processed after cards so a red card doesn't
            # also generate a sub for the same player this interval.
            _roll_and_apply_injuries_and_subs(
                rng, state, input_data, interval_start, interval_end, config
            )

            # Decay fitness — tactic fatigue_mult scales decay rate.
            # HIGH_PRESS teams tire faster; PARK_THE_BUS teams conserve energy.
            home_decay = config.fitness_decay_per_interval * home_profile.fatigue_mult
            away_decay = config.fitness_decay_per_interval * away_profile.fatigue_mult
            _decay_fitness_selective(state, home_decay, away_decay,
                                      state.home_active_xi, state.away_active_xi)

        result = _finalize_result(state, input_data, config, rng)
        last_result = result

        # Dixon-Coles rejection sampling
        tau = _compute_tau(result.home_goals, result.away_goals, mu_h, mu_a, config.dixon_coles_rho)
        accept_prob = tau / M

        # Separate RNG seeded from run_seed ^ 0xDEAD_BEEF for acceptance checks
        accept_rng = random.Random(run_seed ^ 0xDEAD_BEEF)
        if accept_rng.random() < accept_prob:
            return result

    return last_result
