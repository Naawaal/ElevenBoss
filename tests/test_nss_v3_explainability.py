# tests/test_nss_v3_explainability.py
from __future__ import annotations

from match_engine.v3 import EventCategory, MatchEventV3, project_explanation


def test_turning_points_deterministic():
    events = [
        MatchEventV3(
            seq=1, minute=0, type="KICKOFF", category=EventCategory.ADMINISTRATIVE,
            payload={"score_update": "0 - 0"},
        ),
        MatchEventV3(
            seq=2, minute=22, type="GOAL", category=EventCategory.SPORTING,
            payload={"actor": "A", "team": "H", "score_update": "1 - 0"},
            causal_hint="build_up",
        ),
        MatchEventV3(
            seq=3, minute=67, type="GOAL", category=EventCategory.SPORTING,
            payload={"actor": "B", "team": "A", "score_update": "1 - 1"},
        ),
        MatchEventV3(
            seq=4, minute=90, type="FULL_TIME", category=EventCategory.ADMINISTRATIVE,
            payload={"score_update": "1 - 1"},
        ),
    ]
    a = project_explanation(events, result="draw")
    b = project_explanation(events, result="draw")
    assert a.headline == b.headline
    assert a.turning_points == b.turning_points
    assert a.primary_turning_seq == 3
    assert len(a.turning_points) == 2
    assert a.turning_points[0]["causal_hint"] == "build up"


def test_goal_keeps_causal_hint():
    events = [
        MatchEventV3(
            seq=1, minute=10, type="GOAL", category=EventCategory.SPORTING,
            payload={"actor": "Striker", "team": "H", "score_update": "1 - 0"},
            causal_hint="counter_attack",
        ),
    ]
    expl = project_explanation(events, result="win")
    assert expl.turning_points[0]["causal_hint"] == "counter attack"
    assert expl.turning_points[0]["text_key"] == "goal"


def test_includes_tactical_decision_and_window():
    events = [
        MatchEventV3(
            seq=1, minute=15, type="DECISION_WINDOW", category=EventCategory.ADMINISTRATIVE,
            payload={"score_update": "0 - 0"},
        ),
        MatchEventV3(
            seq=2, minute=30, type="TACTICAL_DECISION", category=EventCategory.DECISION,
            payload={"tactic": "High Press", "team": "H", "score_update": "0 - 0", "actor": "Manager"},
        ),
        MatchEventV3(
            seq=3, minute=90, type="FULL_TIME", category=EventCategory.ADMINISTRATIVE,
            payload={"score_update": "0 - 0"},
        ),
    ]
    expl = project_explanation(events, result="draw")
    types = {t["type"] for t in expl.turning_points}
    assert "DECISION_WINDOW" in types
    assert "TACTICAL_DECISION" in types
    tactical = next(t for t in expl.turning_points if t["type"] == "TACTICAL_DECISION")
    assert "High Press" in tactical["causal_hint"]


def test_admin_only_stream_no_invented_tips():
    events = [
        MatchEventV3(
            seq=1, minute=0, type="KICKOFF", category=EventCategory.ADMINISTRATIVE,
            payload={"score_update": "0 - 0"},
        ),
        MatchEventV3(
            seq=2, minute=90, type="FULL_TIME", category=EventCategory.ADMINISTRATIVE,
            payload={"score_update": "0 - 0"},
        ),
    ]
    expl = project_explanation(events, result="draw")
    assert expl.turning_points == []
    assert expl.primary_turning_seq is None
    assert expl.headline  # result-flavored headline still ok


def test_chance_fallback_when_no_goals():
    events = [
        MatchEventV3(
            seq=1, minute=12, type="CHANCE", category=EventCategory.SPORTING,
            payload={"team": "H", "score_update": "0 - 0"},
        ),
        MatchEventV3(
            seq=2, minute=40, type="CHANCE", category=EventCategory.SPORTING,
            payload={"team": "A", "score_update": "0 - 0"},
        ),
        MatchEventV3(
            seq=3, minute=70, type="CHANCE", category=EventCategory.SPORTING,
            payload={"team": "H", "score_update": "0 - 0"},
        ),
    ]
    expl = project_explanation(events, result="draw")
    assert len(expl.turning_points) == 1
    assert expl.turning_points[0]["type"] == "CHANCE"
    assert expl.turning_points[0]["seq"] == 2  # mid chance
