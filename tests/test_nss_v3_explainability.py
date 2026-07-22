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
