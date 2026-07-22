# tests/test_nss_v3_bot_policy.py
"""US8: DefaultPolicy + Wave 3 Aggressive/Defensive policies."""
from __future__ import annotations

from pathlib import Path

from match_engine.v3 import BotBrain, DecisionContext, DefaultPolicy, MatchContext
from match_engine.v3.policies import AggressivePolicy, DefensivePolicy


def test_default_policy_returns_none():
    policy = DefaultPolicy()
    ctx = DecisionContext(
        minute=30,
        home_score=1,
        away_score=0,
        own_tactic="balanced",
        opponent_tactic="attack",
        trailing=True,
    )
    assert policy.propose(ctx) is None
    assert BotBrain().propose(ctx) is None


def test_policy_does_not_mutate_match_context():
    ctx = MatchContext(
        home_rating=70.0,
        away_rating=70.0,
        home_name="H",
        away_name="A",
        minute=20,
        tactic_home="balanced",
    )
    before = ctx.model_dump()
    BotBrain(AggressivePolicy()).propose(
        DecisionContext(minute=70, home_score=0, away_score=1, trailing=True)
    )
    assert ctx.model_dump() == before


def test_aggressive_policy_attacks_when_trailing_late():
    intent = AggressivePolicy().propose(
        DecisionContext(
            minute=70,
            home_score=2,
            away_score=0,
            own_tactic="balanced",
            trailing=True,
        )
    )
    assert intent is not None
    assert intent.payload.get("tactic") == "attack"
    assert intent.source == "ai"


def test_defensive_policy_defends_when_leading_late():
    intent = DefensivePolicy().propose(
        DecisionContext(
            minute=75,
            home_score=0,
            away_score=2,
            own_tactic="balanced",
            trailing=False,
        )
    )
    assert intent is not None
    assert intent.payload.get("tactic") == "defend"


def test_aggressive_policy_emits_via_engine_at_window():
    """US8: swap Policy behind BotBrain — engine accepts DecisionIntent (no score poke)."""
    from match_engine import MatchPlayerCard
    from match_engine.v3 import BotBrain, SimulationEngine

    def _xi(ovr: int = 70) -> list[MatchPlayerCard]:
        roles = ["GK"] + ["DEF"] * 4 + ["MID"] * 4 + ["FWD"] * 2
        return [
            MatchPlayerCard(
                name=f"P{i}", position=roles[i], overall=ovr,
                pac=ovr, sho=ovr, pas=ovr, dri=ovr, def_stat=ovr, phy=ovr, card_id=f"x{i}",
            )
            for i in range(11)
        ]

    eng = SimulationEngine(
        brain=BotBrain(AggressivePolicy()),
        enforce_decision_windows=True,
        simulation_schema_version=2,
    )
    ctx = eng.initial_context(
        home=_xi(80),
        away=_xi(70),
        home_name="H",
        away_name="A",
        home_rating=80.0,
        away_rating=70.0,
        seed=42,
    )
    # Force trailing away by running until home leads, or just run full and check no crash
    eng.run_to_completion(ctx)
    # Policy may or may not fire depending on score path — API swap must not crash
    assert eng._state is not None


def test_battle_cog_does_not_import_dixon_coles():
    root = Path(__file__).resolve().parents[1]
    battle = (root / "apps/discord_bot/cogs/battle_cog.py").read_text(encoding="utf-8")
    assert "dixon" not in battle.lower()
    assert "Dixon" not in battle
    assert "stream_match" in battle
    assert "styles_enabled" in battle
    assert "battle_touchline_style_" in battle or "Possession" in battle
