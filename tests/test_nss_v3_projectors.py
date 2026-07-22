# tests/test_nss_v3_projectors.py
from __future__ import annotations

from match_engine.v3 import EventCategory, MatchEventV3, project_box_score, sporting_digest


def test_box_score_from_goals_and_shots():
    events = [
        MatchEventV3(
            seq=1, minute=0, type="KICKOFF", category=EventCategory.ADMINISTRATIVE,
            payload={"team": "Home", "score_update": "0 - 0", "actor": "ref"},
        ),
        MatchEventV3(
            seq=2, minute=12, type="GOAL", category=EventCategory.SPORTING,
            payload={"team": "Home", "actor": "Striker", "score_update": "1 - 0"},
        ),
        MatchEventV3(
            seq=3, minute=40, type="MISS", category=EventCategory.SPORTING,
            payload={"team": "Away", "actor": "Winger", "score_update": "1 - 0"},
        ),
        MatchEventV3(
            seq=4, minute=90, type="FULL_TIME", category=EventCategory.ADMINISTRATIVE,
            payload={"score_update": "1 - 0"},
        ),
    ]
    box = project_box_score(events, home_name="Home")
    assert box.goals_home == 1
    assert box.goals_away == 0
    assert box.shots_home >= 1
    assert box.shots_away >= 1
    assert box.motm_name == "Striker"


def test_projection_excluded_from_sporting():
    base = [
        MatchEventV3(
            seq=1, minute=0, type="KICKOFF", category=EventCategory.ADMINISTRATIVE,
            payload={"score_update": "0 - 0", "actor": "r", "team": "H"},
        ),
        MatchEventV3(
            seq=2, minute=1, type="PROJECTION_COMMENTARY", category=EventCategory.PROJECTION,
            payload={"text": "x"},
        ),
        MatchEventV3(
            seq=3, minute=90, type="FULL_TIME", category=EventCategory.ADMINISTRATIVE,
            payload={"score_update": "0 - 0"},
        ),
    ]
    without = [e for e in base if e.category != EventCategory.PROJECTION]
    assert sporting_digest(base, home_score=0, away_score=0) == sporting_digest(
        without, home_score=0, away_score=0
    )
