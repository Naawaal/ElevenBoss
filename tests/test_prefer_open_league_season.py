# tests/test_prefer_open_league_season.py
from __future__ import annotations

from leagues import prefer_open_league_season


def test_prefer_active_over_stale_registration() -> None:
    seasons = [
        {"id": "old", "status": "registration", "created_at": "2026-07-17T00:00:00+00:00"},
        {"id": "live", "status": "active", "created_at": "2026-07-20T00:00:00+00:00"},
    ]
    pick = prefer_open_league_season(seasons)
    assert pick is not None
    assert pick["id"] == "live"


def test_prefer_active_even_if_registration_is_newer() -> None:
    """Leftover or premature registration must not hide an in-play season."""
    seasons = [
        {"id": "live", "status": "active", "created_at": "2026-07-20T00:00:00+00:00"},
        {"id": "next", "status": "registration_open", "created_at": "2026-07-22T00:00:00+00:00"},
    ]
    pick = prefer_open_league_season(seasons)
    assert pick is not None
    assert pick["id"] == "live"


def test_prefer_newest_among_same_status() -> None:
    seasons = [
        {"id": "a", "status": "registration", "created_at": "2026-07-01T00:00:00+00:00"},
        {"id": "b", "status": "registration", "created_at": "2026-07-10T00:00:00+00:00"},
    ]
    pick = prefer_open_league_season(seasons)
    assert pick is not None
    assert pick["id"] == "b"


def test_prefer_ignores_completed() -> None:
    seasons = [
        {"id": "done", "status": "completed", "created_at": "2026-07-20T00:00:00+00:00"},
        {"id": "reg", "status": "registration", "created_at": "2026-07-21T00:00:00+00:00"},
    ]
    pick = prefer_open_league_season(seasons)
    assert pick is not None
    assert pick["id"] == "reg"
