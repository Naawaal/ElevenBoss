# packages/leagues/leagues/operation_keys.py
"""Exactly-once operation key builders for League Lifecycle V1."""
from __future__ import annotations


def season_registration_close(season_id: str) -> str:
    return f"season:{season_id}:registration_close"


def season_prepare(season_id: str) -> str:
    return f"season:{season_id}:prepare"


def season_activate(season_id: str) -> str:
    return f"season:{season_id}:activate"


def matchday_open(matchday_id: str) -> str:
    return f"matchday:{matchday_id}:open"


def matchday_remind(matchday_id: str) -> str:
    return f"matchday:{matchday_id}:remind"


def matchday_lock(matchday_id: str) -> str:
    return f"matchday:{matchday_id}:lock"


def matchday_complete(matchday_id: str) -> str:
    return f"matchday:{matchday_id}:complete"


def fixture_resolve(fixture_id: str) -> str:
    return f"fixture:{fixture_id}:resolve"


def fixture_settle(fixture_id: str) -> str:
    return f"fixture:{fixture_id}:settle"


def season_settle(season_id: str) -> str:
    return f"season:{season_id}:settle"


def season_promotion(season_id: str) -> str:
    return f"season:{season_id}:promotion"


def season_rewards(season_id: str) -> str:
    return f"season:{season_id}:rewards"


def season_next_registration(season_id: str) -> str:
    return f"season:{season_id}:next_registration"
