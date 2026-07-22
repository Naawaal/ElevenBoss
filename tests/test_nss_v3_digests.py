# tests/test_nss_v3_digests.py
from __future__ import annotations

from match_engine.v3 import (
    EventCategory,
    MatchEventV3,
    deterministic_replay_digest,
    settlement_digest,
    sporting_digest,
)


def test_projection_excluded_from_sporting_and_replay():
    base = [
        MatchEventV3(
            seq=1,
            minute=0,
            type="KICKOFF",
            category=EventCategory.ADMINISTRATIVE,
            payload={"actor": "ref", "team": "H", "score_update": "0 - 0"},
        ),
        MatchEventV3(
            seq=2,
            minute=10,
            type="GOAL",
            category=EventCategory.SPORTING,
            payload={"actor": "A", "team": "H", "score_update": "1 - 0"},
        ),
        MatchEventV3(
            seq=3,
            minute=10,
            type="PROJECTION_COMMENTARY",
            category=EventCategory.PROJECTION,
            payload={"text": "ignore me"},
        ),
        MatchEventV3(
            seq=4,
            minute=90,
            type="FULL_TIME",
            category=EventCategory.ADMINISTRATIVE,
            payload={"score_update": "1 - 0"},
        ),
    ]
    without_proj = [e for e in base if e.category != EventCategory.PROJECTION]
    assert sporting_digest(without_proj, home_score=1, away_score=0) == sporting_digest(
        base, home_score=1, away_score=0
    )
    # Replay also skips Projection category
    assert deterministic_replay_digest(base) == deterministic_replay_digest(without_proj)


def test_settlement_digest_stable():
    a = settlement_digest({"coins": 100, "xp_total": 40, "run_id": "x"})
    b = settlement_digest({"coins": 100, "xp_total": 40, "run_id": "x"})
    c = settlement_digest({"coins": 101, "xp_total": 40, "run_id": "x"})
    assert a == b
    assert a != c
