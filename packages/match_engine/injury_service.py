# app/engine/injury_service.py
"""
Pure function for rolling in-match injuries during the interval loop.

Design rules (engine purity):
  - No imports from packages.models, packages.db, app.services, or Discord.
  - Does NOT mutate state — returns events only. Mutation (fitness reduction,
    triggering subs) is handled by the loop in match_engine.py.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from .match_config import MatchEngineConfig

if TYPE_CHECKING:
    from .match_engine import MatchPlayerInput


def roll_injuries_for_interval(
    rng: random.Random,
    home_active_xi: list[MatchPlayerInput],
    away_active_xi: list[MatchPlayerInput],
    home_club_id: str,
    away_club_id: str,
    fitness: dict[str, float],
    injured_player_ids: set[str],
    interval_start: int,
    interval_end: int,
    config: MatchEngineConfig,
) -> list[tuple[str, str, MatchPlayerInput, int]]:
    """
    Roll for injuries across both teams for a single match interval.

    Injury probability per player scales with fatigue:
      p = injury_base_probability × (1.0 + (1.0 - current_fitness))

    This means a fully fresh player (fitness=1.0) rolls at the base rate,
    and a completely spent player (fitness=0.0) rolls at 2× base rate.
    Players already injured this match are skipped.

    Args:
        rng: Local Random instance (deterministic).
        home_active_xi / away_active_xi: Current active player lists.
        home_club_id / away_club_id: Club IDs for event attribution.
        fitness: Current fitness dict (player_id -> 0.0–1.0 fraction).
        injured_player_ids: Set of player IDs already injured; skipped here.
        interval_start / interval_end: Minute bounds for this interval.
        config: MatchEngineConfig with injury_base_probability field.

    Returns:
        List of (team_side, club_id, player, minute) tuples for each
        injury that occurred. Does NOT mutate state.
    """
    injuries: list[tuple[str, str, MatchPlayerInput, int]] = []

    teams = [
        ("home", home_club_id, home_active_xi),
        ("away", away_club_id, away_active_xi),
    ]

    for team_side, club_id, active_xi in teams:
        for player in active_xi:
            if player.player_id in injured_player_ids:
                continue  # already injured — skip to avoid double-rolling

            current_fitness = fitness.get(player.player_id, 1.0)
            # Probability scales linearly from base at fitness=1.0 to 2×base at fitness=0.0
            p_injury = config.injury_base_probability * (1.0 + (1.0 - current_fitness))

            if rng.random() < p_injury:
                minute = rng.randint(interval_start, interval_end)
                injuries.append((team_side, club_id, player, minute))

    return injuries
