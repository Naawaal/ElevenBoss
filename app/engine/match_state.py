# app/engine/match_state.py
"""
Mutable match state threaded through the interval simulation loop.

Field ordering: non-default fields first (Python dataclass requirement).
Fitness is stored as a separate dict keyed by player_id because MatchPlayerInput
is frozen=True and cannot be mutated mid-match.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.match_engine import (
        MatchPlayerInput,
        MatchSimulationInput,
        MatchGoalEvent,
        MatchCardEvent,
    )


@dataclass
class MatchState:
    # --- Required fields (no defaults) — must come first in dataclass ---
    home_active_xi: list[MatchPlayerInput]
    """Current active home players. Red cards remove entries from this list."""

    away_active_xi: list[MatchPlayerInput]
    """Current active away players. Red cards remove entries from this list."""

    fitness: dict[str, float]
    """player_id -> current fitness as a 0.0–1.0 fraction. Decays each interval."""

    # --- Defaulted fields ---
    home_score: int = 0
    away_score: int = 0
    home_red_cards: int = 0
    away_red_cards: int = 0
    home_subs_used: int = 0
    away_subs_used: int = 0
    events: list = field(default_factory=list)
    """Chronological list of MatchGoalEvent, MatchCardEvent, MatchSubstitutionEvent, MatchInjuryEvent."""

    injured_player_ids: set = field(default_factory=set)
    """Player IDs that have received an injury event this match (to avoid double-rolling)."""


    # Per-interval strength delta accumulators for possession and shots rollup.
    # Populated by the loop so _finalize_result() can average across the full
    # match rather than snapshot only the final interval.
    home_midfield_deltas: list = field(default_factory=list)
    """(home_midfield - away_midfield) sampled at the start of each interval."""
    home_attack_deltas: list = field(default_factory=list)
    """(home_attack - away_defense) sampled at the start of each interval."""
    away_attack_deltas: list = field(default_factory=list)
    """(away_attack - home_defense) sampled at the start of each interval."""


    @classmethod
    def initial(cls, sim_input: MatchSimulationInput) -> MatchState:
        """
        Build the starting state from simulation inputs.

        Fitness is initialised from player.fitness (0–100 integer) normalised
        to a 0.0–1.0 float. Active XIs are shallow copies so the originals are
        not mutated when players are removed mid-match.
        """
        all_players = list(sim_input.home_team.players) + list(sim_input.away_team.players)
        fitness = {p.player_id: max(0.0, min(1.0, p.fitness / 100.0)) for p in all_players}
        return cls(
            home_active_xi=list(sim_input.home_team.players),
            away_active_xi=list(sim_input.away_team.players),
            fitness=fitness,
        )
