"""US-42.3 club action matrix + soft lifecycle pure tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from player_engine.club_state import (
    can_perform_club_action,
    derive_club_kind,
    soft_lifecycle_from_activity,
)
from player_engine.identity import ABANDONED_DAYS, INACTIVE_DAYS


def test_soft_thresholds_align_with_identity():
    now = datetime(2026, 7, 22, tzinfo=timezone.utc)
    assert soft_lifecycle_from_activity(now - timedelta(days=29), now) == "Active"
    assert soft_lifecycle_from_activity(now - timedelta(days=INACTIVE_DAYS), now) == "Inactive"
    assert soft_lifecycle_from_activity(now - timedelta(days=ABANDONED_DAYS), now) == "Abandoned"


def test_ai_kind():
    assert derive_club_kind(is_ai=True) == "AI"
    assert derive_club_kind(is_ai=False) == "Human"


@pytest.mark.parametrize(
    "soft,kind,match_locked,action,allowed",
    [
        ("Inactive", "Human", False, "league_join", False),
        ("Abandoned", "Human", False, "league_join", False),
        ("Active", "Human", False, "league_join", True),
        ("Inactive", "Human", False, "store_faucet", True),
        ("Inactive", "Human", False, "development_mutate", True),
        ("Abandoned", "Human", False, "recover", True),
        ("Active", "Human", False, "view_hub", True),
        ("Active", "AI", False, "league_join", False),
        ("Active", "AI", False, "store_faucet", False),
        ("Active", "AI", False, "development_mutate", False),
        ("Active", "Human", True, "match_start", False),
        ("Active", "Human", True, "league_join", False),
        ("Active", "Human", True, "view_hub", True),
        ("Active", "Human", True, "store_faucet", True),
        ("Inactive", "Human", True, "recover", True),
    ],
)
def test_club_matrix_cells(soft, kind, match_locked, action, allowed):
    ok, reason = can_perform_club_action(
        soft, kind=kind, match_locked=match_locked, action=action
    )
    assert ok is allowed, (soft, action, reason)
    if allowed:
        assert reason == ""
    else:
        assert reason.startswith("CLUB_STATE:")
