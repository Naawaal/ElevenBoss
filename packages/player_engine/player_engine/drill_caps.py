# packages/player_engine/player_engine/drill_caps.py
"""Club/per-card daily drill cap helpers (display mirrors RPC soft-reset)."""
from __future__ import annotations

from datetime import date

CLUB_DAILY_DRILL_LIMIT = 20
CARD_DAILY_DRILL_LIMIT = 5


def effective_daily_drill_count(
    count: int,
    reset_at: date | None,
    *,
    today: date,
) -> int:
    """Mirror process_stat_drill / process_recovery_session soft-reset for hub UI."""
    if reset_at is None or reset_at < today:
        return 0
    return max(0, int(count))
