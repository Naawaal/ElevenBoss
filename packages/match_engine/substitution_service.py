# app/engine/substitution_service.py
"""
Substitution logic for the interval-based simulation loop.

Design rules (engine purity):
  - No imports from packages.models, packages.db, app.services, or Discord.
  - These functions DO mutate state (active XI replacement, subs counter, fitness).
    This is intentional: substitution_service.py is the designated mutation owner
    for substitution state, analogous to how _roll_and_apply_cards() owns card mutations.

Caller responsibility:
  - Check config.max_substitutions against state.home_subs_used / away_subs_used
    BEFORE calling these functions.
  - These functions assume subs are still available when called.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from .match_config import MatchEngineConfig

if TYPE_CHECKING:
    from .match_engine import MatchPlayerInput, MatchTeamInput


def _pick_replacement(
    rng: random.Random,
    player_out: MatchPlayerInput,
    bench: list[MatchPlayerInput],
    active_ids: set[str],
) -> MatchPlayerInput | None:
    """
    Select the best available bench player to replace `player_out`.

    Preference order:
      1. Same position group (e.g. striker out → striker from bench)
      2. Compatible position group
      3. Any outfield player (if GK slot is not involved)

    Returns None if bench is empty or all bench players are already on the field.
    """
    available = [p for p in bench if p.player_id not in active_ids]
    if not available:
        return None

    # Prefer exact position match
    exact = [p for p in available if p.position == player_out.position]
    if exact:
        return rng.choice(exact)

    # Prefer same slot group (GK/DEF/MID/ATT)
    def slot_group(slot: str) -> str:
        s = slot.upper()
        if "GK" in s:
            return "GK"
        if any(x in s for x in ("LB", "CB", "RB", "LWB", "RWB", "DEF")):
            return "DEF"
        if any(x in s for x in ("LM", "CM", "RM", "LDM", "RDM", "CAM", "CDM", "MID")):
            return "MID"
        return "ATT"

    target_group = slot_group(player_out.slot)
    same_group = [p for p in available if slot_group(p.slot) == target_group]
    if same_group:
        return rng.choice(same_group)

    # Fall back to any outfield player (never sub a GK unless the slot demands it)
    if target_group != "GK":
        outfield = [p for p in available if slot_group(p.slot) != "GK"]
        if outfield:
            return rng.choice(outfield)

    return rng.choice(available)


def _apply_sub(
    state,
    team_side: str,
    player_out: MatchPlayerInput,
    player_in: MatchPlayerInput,
) -> None:
    """
    Mutate state to reflect a completed substitution.

    - Replaces player_out with player_in in the active XI list.
    - Initialises player_in's fitness to 1.0 (fresh from bench).
    - Increments the appropriate subs_used counter.
    """
    import dataclasses
    active_xi: list[MatchPlayerInput] = (
        state.home_active_xi if team_side == "home" else state.away_active_xi
    )
    idx = next(i for i, p in enumerate(active_xi) if p.player_id == player_out.player_id)
    
    # Inherit the subbed-out player's slot to prevent active XI collisions
    mutated_player_in = dataclasses.replace(player_in, slot=player_out.slot)
    active_xi[idx] = mutated_player_in
    state.fitness[player_in.player_id] = 1.0

    if team_side == "home":
        state.home_subs_used += 1
    else:
        state.away_subs_used += 1


def try_fatigue_sub(
    rng: random.Random,
    state,
    team_side: str,
    team: MatchTeamInput,
    interval_start: int,
    interval_end: int,
    config: MatchEngineConfig,
):
    """
    Attempt a fatigue-driven substitution for one team in one interval.

    Checks for the most fatigued outfield player below `config.fatigue_sub_threshold`.
    GKs are excluded — goalkeepers are never subbed off for fatigue here.
    Returns a MatchSubstitutionEvent or None (no sub triggered / bench empty / limit reached).

    Mutates: state.home_active_xi / away_active_xi, state.fitness, state.home/away_subs_used.
    """
    from .match_engine import MatchSubstitutionEvent

    subs_used = state.home_subs_used if team_side == "home" else state.away_subs_used
    if subs_used >= config.max_substitutions:
        return None

    active_xi: list[MatchPlayerInput] = (
        state.home_active_xi if team_side == "home" else state.away_active_xi
    )

    # Find outfield players below the fatigue threshold
    fatigued = [
        p for p in active_xi
        if p.slot.upper() != "GK"
        and state.fitness.get(p.player_id, 1.0) < config.fatigue_sub_threshold
    ]
    if not fatigued:
        return None

    # Sub off the most fatigued player
    player_out = min(fatigued, key=lambda p: state.fitness.get(p.player_id, 1.0))
    active_ids = {p.player_id for p in active_xi}
    player_in = _pick_replacement(rng, player_out, team.bench, active_ids)
    if player_in is None:
        return None

    _apply_sub(state, team_side, player_out, player_in)
    minute = rng.randint(interval_start, interval_end)

    desc = (
        f"Substitution ({team.club_name}): {player_in.name} replaces {player_out.name} "
        f"(fatigue, {int(state.fitness.get(player_out.player_id, 0.0) * 100 + config.fitness_decay_per_interval * 100):.0f}% fitness)."
    )
    return MatchSubstitutionEvent(
        minute=minute,
        club_id=team.club_id,
        player_out_id=player_out.player_id,
        player_in_id=player_in.player_id,
        reason="fatigue",
        description=desc,
    )


def force_injury_sub(
    rng: random.Random,
    state,
    team_side: str,
    team: MatchTeamInput,
    injured_player: MatchPlayerInput,
    minute: int,
    config: MatchEngineConfig,
):
    """
    Attempt a forced substitution to replace an injured player.

    Unlike fatigue subs, injury subs ignore the fatigue threshold — they happen
    immediately regardless of the injured player's fitness reading.
    Returns a MatchSubstitutionEvent or None (bench empty / sub limit reached).

    Mutates: state.home_active_xi / away_active_xi, state.fitness, state.home/away_subs_used.
    """
    from .match_engine import MatchSubstitutionEvent

    subs_used = state.home_subs_used if team_side == "home" else state.away_subs_used
    if subs_used >= config.max_substitutions:
        # No subs left — injured player stays on (fitness already set to near 0 by caller)
        return None

    active_xi: list[MatchPlayerInput] = (
        state.home_active_xi if team_side == "home" else state.away_active_xi
    )

    # Check the injured player is still on the field (not already subbed/red-carded)
    if not any(p.player_id == injured_player.player_id for p in active_xi):
        return None

    active_ids = {p.player_id for p in active_xi}
    player_in = _pick_replacement(rng, injured_player, team.bench, active_ids)
    if player_in is None:
        return None

    _apply_sub(state, team_side, injured_player, player_in)

    desc = (
        f"Substitution ({team.club_name}): {player_in.name} replaces {injured_player.name} "
        f"(injury)."
    )
    return MatchSubstitutionEvent(
        minute=minute,
        club_id=team.club_id,
        player_out_id=injured_player.player_id,
        player_in_id=player_in.player_id,
        reason="injury",
        description=desc,
    )
