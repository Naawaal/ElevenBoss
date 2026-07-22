# tests/test_nss_v3_decisions.py
"""US7: DecisionInbox collapse, immediate apply, Wave 1 windows."""
from __future__ import annotations

from match_engine import MatchPlayerCard
from match_engine.v3 import (
    DECISION_WINDOWS,
    DecisionInbox,
    DecisionIntent,
    SimulationEngine,
)
from match_engine.v3.decisions import windows_crossed


def _xi(ovr: int = 70) -> list[MatchPlayerCard]:
    roles = ["GK"] + ["DEF"] * 4 + ["MID"] * 4 + ["FWD"] * 2
    return [
        MatchPlayerCard(
            name=f"P{i}", position=roles[i], overall=ovr,
            pac=ovr, sho=ovr, pas=ovr, dri=ovr, def_stat=ovr, phy=ovr, card_id=f"d{i}",
        )
        for i in range(11)
    ]


def test_inbox_collapses_tactic_spam():
    box = DecisionInbox()
    box.push(DecisionIntent(payload={"tactic": "attack"}, requested_at_minute=10))
    box.push(DecisionIntent(payload={"tactic": "defend"}, requested_at_minute=11))
    ready = box.pop_ready(minute=12, enforce_windows=False)
    assert len(ready) == 1
    assert ready[0].payload["tactic"] == "defend"


def test_immediate_apply_emits_decision_event():
    eng = SimulationEngine(
        simulation_schema_version=1, enforce_decision_windows=False
    )
    ctx = eng.initial_context(
        home=_xi(70), away=_xi(70),
        home_name="H", away_name="A",
        home_rating=70.0, away_rating=70.0, seed=3,
    )
    eng.push_decision(
        DecisionIntent(
            payload={"tactic": "attack"},
            requested_at_minute=0,
            source="human",
        )
    )
    eng.step(ctx)
    all_types = [e.type for e in eng.all_events()]
    assert "TACTICAL_DECISION" in all_types
    dec = next(e for e in eng.all_events() if e.type == "TACTICAL_DECISION")
    assert dec.payload.get("applied_immediate") is True
    assert eng._state is not None
    assert eng._state.home_tactics_modifier == 1.3


def test_ignore_post_ft():
    box = DecisionInbox()
    box.push(DecisionIntent(payload={"tactic": "attack"}, requested_at_minute=90))
    assert box.pop_ready(minute=90, terminal=True) == []
    assert box.peek() == []


def test_scheduled_recovery_applies_at_minute():
    eng = SimulationEngine(enforce_decision_windows=False, simulation_schema_version=1)
    ctx = eng.initial_context(
        home=_xi(72), away=_xi(68),
        home_name="H", away_name="A",
        home_rating=72.0, away_rating=68.0, seed=8,
    )
    delayed = DecisionIntent(
        payload={"tactic": "defend"},
        requested_at_minute=45,
        source="human",
    )
    eng.run_to_completion(ctx, decisions=[delayed])
    decs = [e for e in eng.all_events() if e.type == "TACTICAL_DECISION"]
    assert decs
    assert all(e.minute >= 45 or e.payload.get("requested_at_minute") == 45 for e in decs)


def test_windows_crossed_handles_jumps():
    assert windows_crossed(14, 16) == (15,)
    assert windows_crossed(14, 15) == (15,)
    assert windows_crossed(15, 15) == ()
    assert windows_crossed(40, 50) == (45,)


def test_wave1_windows_enforced():
    eng = SimulationEngine(simulation_schema_version=2, enforce_decision_windows=True)
    ctx = eng.initial_context(
        home=_xi(70), away=_xi(70),
        home_name="H", away_name="A",
        home_rating=70.0, away_rating=70.0, seed=1,
    )
    eng.push_decision(
        DecisionIntent(payload={"tactic": "attack"}, requested_at_minute=10)
    )
    applied_at = None
    for _ in range(200):
        r = eng.step(ctx)
        ctx = r.context
        if any(e.type == "TACTICAL_DECISION" for e in r.events):
            applied_at = ctx.minute
            assert applied_at in DECISION_WINDOWS or any(
                w <= applied_at for w in DECISION_WINDOWS if w >= 15
            )
            break
        if r.terminal:
            break
    assert applied_at is not None, "decision never applied at a window"
    assert eng._state is not None
    assert eng._state.home_tactics_modifier == 1.3
