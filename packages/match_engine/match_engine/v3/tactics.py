# packages/match_engine/match_engine/v3/tactics.py
"""Stance modifiers (Phase 0) + TransitionProfiles (Wave 2)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TransitionProfile(BaseModel):
    """
    Alters transition weights/timings — not primary SCORING_OPP goal% padding (FR-011).
    Defaults match NSS v2 when name is balanced / attack / defend (stance only).
    """

    name: str
    build_up_clock_mult: float = 1.0
    counter_weight: float = 1.0
    set_piece_rate: float = 0.08
    press_rate: float = 1.0
    fatigue_pressure: float = 1.0
    stance_modifier: float = 1.0


PHASE0_STANCES: dict[str, float] = {
    "attack": 1.3,
    "attacking": 1.3,
    "balanced": 1.0,
    "defend": 0.7,
    "defending": 0.7,
}


# Wave 2 named styles (plus stance aliases)
TRANSITION_PROFILES: dict[str, TransitionProfile] = {
    "balanced": TransitionProfile(name="balanced"),
    "attack": TransitionProfile(name="attack", stance_modifier=1.3),
    "attacking": TransitionProfile(name="attacking", stance_modifier=1.3),
    "defend": TransitionProfile(name="defend", stance_modifier=0.7),
    "defending": TransitionProfile(name="defending", stance_modifier=0.7),
    "possession": TransitionProfile(
        name="possession",
        build_up_clock_mult=1.35,
        counter_weight=0.55,
        set_piece_rate=0.06,
        press_rate=0.85,
        fatigue_pressure=0.9,
    ),
    "counter": TransitionProfile(
        name="counter",
        build_up_clock_mult=0.8,
        counter_weight=1.55,
        set_piece_rate=0.07,
        press_rate=1.1,
        fatigue_pressure=1.05,
    ),
    "long_ball": TransitionProfile(
        name="long_ball",
        build_up_clock_mult=0.7,
        counter_weight=1.2,
        set_piece_rate=0.1,
        press_rate=0.95,
        fatigue_pressure=1.0,
    ),
    "high_press": TransitionProfile(
        name="high_press",
        build_up_clock_mult=0.95,
        counter_weight=1.15,
        set_piece_rate=0.12,
        press_rate=1.35,
        fatigue_pressure=1.2,
        stance_modifier=1.15,
    ),
}


def phase0_stance_modifier(name: str) -> float:
    return PHASE0_STANCES.get((name or "balanced").lower(), 1.0)


def get_transition_profile(name: str | None) -> TransitionProfile:
    key = (name or "balanced").lower().replace(" ", "_").replace("-", "_")
    if key in TRANSITION_PROFILES:
        return TRANSITION_PROFILES[key]
    # Unknown → balanced transitions + Phase 0 stance if recognizable
    return TransitionProfile(
        name=key,
        stance_modifier=phase0_stance_modifier(key),
    )


def apply_profile_to_state(state: object, profile: TransitionProfile) -> None:
    """Write Wave 2 knobs onto MatchState (no Discord). Always reset stance with the profile."""
    state.build_up_clock_mult = profile.build_up_clock_mult  # type: ignore[attr-defined]
    state.counter_weight = profile.counter_weight  # type: ignore[attr-defined]
    state.set_piece_rate = profile.set_piece_rate * profile.press_rate  # type: ignore[attr-defined]
    state.transition_style = profile.name  # type: ignore[attr-defined]
    # Always assign — Attack→Possession must clear leftover 1.3 stance
    state.home_tactics_modifier = profile.stance_modifier  # type: ignore[attr-defined]
