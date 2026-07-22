# tests/test_nss_v3_tactics_distinguishability.py
"""SC-005: Possession vs Counter transition profiles are distinguishable."""
from __future__ import annotations

from match_engine import MatchPlayerCard
from match_engine.v3 import SimulationEngine


def _xi(ovr: int, tag: str) -> list[MatchPlayerCard]:
    roles = ["GK"] + ["DEF"] * 4 + ["MID"] * 4 + ["FWD"] * 2
    return [
        MatchPlayerCard(
            name=f"{tag}{i}", position=roles[i], overall=ovr,
            pac=ovr, sho=ovr, pas=ovr, dri=ovr, def_stat=ovr, phy=ovr, card_id=f"{tag}{i}",
        )
        for i in range(11)
    ]


def _mean_counters(style: str, n: int = 40) -> float:
    total = 0
    home, away = _xi(75, "H"), _xi(75, "A")
    for seed in range(n):
        eng = SimulationEngine(simulation_schema_version=2)
        ctx = eng.initial_context(
            home=home,
            away=away,
            home_name="H",
            away_name="A",
            home_rating=75.0,
            away_rating=75.0,
            seed=10_000 + seed,
            tactics_home=style,
        )
        eng.run_to_completion(ctx)
        assert eng._state is not None
        total += int(eng._state.counters_triggered)
    return total / n


def test_counter_triggers_more_counters_than_possession():
    c_mean = _mean_counters("counter", n=36)
    p_mean = _mean_counters("possession", n=36)
    # Blind-ish: counter profile should produce clearly more counters
    assert c_mean > p_mean * 1.15, f"counter={c_mean:.2f} possession={p_mean:.2f}"
    # Simple 2-class accuracy proxy on means separation
    assert c_mean - p_mean >= 1.0


def test_balanced_profile_keeps_v2_knob_defaults():
    eng = SimulationEngine()
    ctx = eng.initial_context(
        home=_xi(70, "H"),
        away=_xi(70, "A"),
        home_name="H",
        away_name="A",
        home_rating=70.0,
        away_rating=70.0,
        seed=1,
        tactics_home="balanced",
    )
    assert eng._state is not None
    assert eng._state.counter_weight == 1.0
    assert eng._state.build_up_clock_mult == 1.0
    assert abs(eng._state.set_piece_rate - 0.08) < 1e-9


def test_mid_match_style_applies_transition_profile():
    """US6: DecisionIntent with Wave 2 style updates MatchState knobs."""
    from match_engine.v3 import DecisionIntent

    eng = SimulationEngine(enforce_decision_windows=False, simulation_schema_version=1)
    ctx = eng.initial_context(
        home=_xi(72, "H"),
        away=_xi(70, "A"),
        home_name="H",
        away_name="A",
        home_rating=72.0,
        away_rating=70.0,
        seed=3,
        tactics_home="balanced",
    )
    eng.push_decision(
        DecisionIntent(payload={"tactic": "possession"}, requested_at_minute=0)
    )
    eng.step(ctx)
    assert eng._state is not None
    assert eng._state.transition_style == "possession"
    assert eng._state.counter_weight < 1.0
    assert eng._state.build_up_clock_mult > 1.0


def test_style_after_attack_clears_stance_modifier():
    """Attack→Possession must not leave attack stance 1.3 sticky."""
    from match_engine.v3 import DecisionIntent

    eng = SimulationEngine(enforce_decision_windows=False, simulation_schema_version=1)
    ctx = eng.initial_context(
        home=_xi(72, "H"),
        away=_xi(70, "A"),
        home_name="H",
        away_name="A",
        home_rating=72.0,
        away_rating=70.0,
        seed=4,
        tactics_home="attack",
    )
    assert eng._state is not None
    assert eng._state.home_tactics_modifier == 1.3
    eng.push_decision(
        DecisionIntent(payload={"tactic": "possession"}, requested_at_minute=0)
    )
    eng.step(ctx)
    assert eng._state.transition_style == "possession"
    assert eng._state.home_tactics_modifier == 1.0


def test_style_win_rates_stay_in_even_band():
    """T065: even matchups under Possession/Counter stay in published home band."""
    import asyncio

    from match_engine import MatchState, stream_match_v3

    async def _hw(style: str, n: int = 80) -> float:
        hw = 0
        for i in range(n):
            state = MatchState(home_rating=80.0, away_rating=80.0)
            async for _ in stream_match_v3(
                state,
                _xi(80, "H"),
                _xi(80, "A"),
                "Home",
                "Away",
                sim_seed=20_000 + i,
                tactics_home=style,
            ):
                pass
            if state.home_score > state.away_score:
                hw += 1
        return hw / n

    for style in ("possession", "counter"):
        rate = asyncio.run(_hw(style))
        assert 0.25 <= rate <= 0.55, f"{style} home win {rate:.1%} outside band"
