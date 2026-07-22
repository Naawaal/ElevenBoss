# packages/match_engine/match_engine/v3/adapters.py
"""Discord-facing async adapters over SimulationEngine (sleep-agnostic)."""
from __future__ import annotations

from typing import Any, AsyncGenerator

from match_engine.models import MatchPlayerCard
from match_engine.v2_simulator import MatchState

from .decisions import DecisionInbox, DecisionIntent
from .engine import SimulationEngine
from .events import MatchEventV3


def _sync_state(dst: MatchState, src: MatchState) -> None:
    dst.home_score = src.home_score
    dst.away_score = src.away_score
    dst.minute = src.minute
    dst.momentum = src.momentum
    dst.context_tags = list(src.context_tags)
    dst.home_tactics_modifier = src.home_tactics_modifier
    dst.live_stats = src.live_stats
    dst.subs_used_home = src.subs_used_home
    dst.subs_used_away = src.subs_used_away
    dst.recorded_injuries = list(src.recorded_injuries)
    dst.compromised_card_ids = list(src.compromised_card_ids)
    dst.pending_home_momentum = src.pending_home_momentum
    dst.transition_style = getattr(src, "transition_style", "balanced")
    dst.build_up_clock_mult = getattr(src, "build_up_clock_mult", 1.0)
    dst.counter_weight = getattr(src, "counter_weight", 1.0)
    dst.set_piece_rate = getattr(src, "set_piece_rate", 0.08)
    dst.counters_triggered = getattr(src, "counters_triggered", 0)


def _bind_engine(
    state: MatchState,
    home_squad: list[MatchPlayerCard],
    away_squad: list[MatchPlayerCard],
    home_name: str,
    away_name: str,
    *,
    sim_seed: int,
    tactics_home: str | None = None,
    tactics_away: str | None = None,
    brain: Any | None = None,
) -> tuple[SimulationEngine, Any]:
    style = tactics_home or getattr(state, "transition_style", None) or "balanced"
    eng = SimulationEngine(brain=brain) if brain is not None else SimulationEngine()
    ctx = eng.initial_context(
        home=list(home_squad),
        away=list(away_squad),
        home_name=home_name,
        away_name=away_name,
        home_rating=float(state.home_rating),
        away_rating=float(state.away_rating),
        seed=sim_seed,
        tactics_home=style,
        tactics_away=tactics_away or "balanced",
        intensity_tier=int(getattr(state, "intensity_tier", 1) or 1),
        injuries_enabled=bool(state.injuries_enabled),
        interactive_sides=list(state.interactive_sides or []),
        bench_home=list(getattr(state, "bench_home", None) or []),
        bench_away=list(getattr(state, "bench_away", None) or []),
    )
    if eng._state is not None:
        # Preserve explicit stance if caller already set Attack/Defend before kickoff
        if abs(float(state.home_tactics_modifier) - 1.0) > 1e-6 and style == "balanced":
            eng._state.home_tactics_modifier = state.home_tactics_modifier
        eng._state.pending_home_momentum = state.pending_home_momentum
        _sync_state(state, eng._state)
    return eng, ctx


async def stream_match_v3(
    state: MatchState,
    home_squad: list[MatchPlayerCard],
    away_squad: list[MatchPlayerCard],
    home_name: str,
    away_name: str,
    *,
    sim_seed: int,
    inbox: DecisionInbox | None = None,
    tactics_home: str | None = None,
    brain: Any | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Yield Discord-compat event dicts; caller owns pacing sleeps."""
    eng, ctx = _bind_engine(
        state,
        home_squad,
        away_squad,
        home_name,
        away_name,
        sim_seed=sim_seed,
        tactics_home=tactics_home,
        brain=brain,
    )
    if inbox is not None:
        eng._inbox = inbox
    while not ctx.terminal:
        if eng._state is not None:
            eng._state.pending_home_momentum = state.pending_home_momentum
            if inbox is None:
                eng._state.home_tactics_modifier = state.home_tactics_modifier
        result = eng.step(ctx, eng._inbox)
        ctx = result.context
        if eng._state is not None:
            _sync_state(state, eng._state)
        for ev in result.events:
            yield ev.to_compat_dict()
        if result.terminal:
            break
    setattr(state, "_nss_v3_events", eng.all_events())


async def collect_match_events_v3(
    state: MatchState,
    home_squad: list[MatchPlayerCard],
    away_squad: list[MatchPlayerCard],
    home_name: str,
    away_name: str,
    sim_seed: int,
    *,
    decisions: list[DecisionIntent] | None = None,
    tactics_home: str | None = None,
    brain: Any | None = None,
) -> tuple[MatchState, list[dict[str, Any]], list[MatchEventV3]]:
    """Silent completion; returns compat dicts + canonical events."""
    state.interactive_sides = []
    eng, ctx = _bind_engine(
        state,
        home_squad,
        away_squad,
        home_name,
        away_name,
        sim_seed=sim_seed,
        tactics_home=tactics_home,
        brain=brain,
    )
    ctx2, events = eng.run_to_completion(
        ctx, decisions=decisions, auto_resolve_injuries=True
    )
    if eng._state is not None:
        _sync_state(state, eng._state)
    setattr(state, "_nss_v3_events", events)
    return state, [e.to_compat_dict() for e in events], events
