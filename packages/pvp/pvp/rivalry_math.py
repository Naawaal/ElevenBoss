# packages/pvp/pvp/rivalry_math.py
"""Canonical rivalry pair math — activation, dormancy, streaks, events (Feature 053)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pvp.models import RivalryEvent, RivalryState

ACTIVATION_MEETINGS = 3
ACTIVATION_WINDOW = timedelta(days=30)
DORMANT_AFTER = timedelta(days=60)


def canonical_pair(manager_1: int, manager_2: int) -> tuple[int, int]:
    if manager_1 == manager_2:
        raise ValueError("rivalry pair requires two distinct managers")
    return (manager_1, manager_2) if manager_1 < manager_2 else (manager_2, manager_1)


def refresh_dormancy(state: RivalryState, *, now: datetime | None = None) -> RivalryState:
    """Mark active/tracking rivalries dormant after 60 days without a meeting."""
    now = now or datetime.now(timezone.utc)
    if state.status == "dormant" or state.last_match_at is None:
        return state
    last = state.last_match_at if state.last_match_at.tzinfo else state.last_match_at.replace(tzinfo=timezone.utc)
    if (now - last) >= DORMANT_AFTER:
        return state.model_copy(update={"status": "dormant"})
    return state


def apply_ranked_meeting(
    state: RivalryState,
    *,
    winner_id: int | None,
    home_id: int,
    away_id: int,
    home_goals: int,
    away_goals: int,
    matched_at: datetime | None = None,
) -> tuple[RivalryState, list[RivalryEvent]]:
    """
    Apply one ranked PvP result to a rivalry row.

    Activation rule: status becomes `active` when meetings reach 3 and the span
    from the first meeting in the current activation window to this meeting
    is ≤ 30 days. Window start is tracked via `first_meeting_in_window_at`
    (reset when a meeting lands after a >30d gap from the window start).
    """
    matched_at = matched_at or datetime.now(timezone.utc)
    if matched_at.tzinfo is None:
        matched_at = matched_at.replace(tzinfo=timezone.utc)

    a_id, b_id = canonical_pair(home_id, away_id)
    events: list[RivalryEvent] = []

    prev_a_wins, prev_b_wins = state.a_wins, state.b_wins
    prev_streak_owner = state.current_streak_owner
    prev_streak_count = state.current_streak_count
    was_active = state.status == "active"

    # Goals from A/B perspective
    if home_id == a_id:
        a_g, b_g = home_goals, away_goals
    else:
        a_g, b_g = away_goals, home_goals

    meetings = state.meetings + 1
    a_wins = state.a_wins + (1 if winner_id == a_id else 0)
    b_wins = state.b_wins + (1 if winner_id == b_id else 0)
    draws = state.draws + (1 if winner_id is None else 0)

    # Streak
    if winner_id is None:
        streak_owner: int | None = None
        streak_count = 0
    elif winner_id == state.current_streak_owner:
        streak_owner = winner_id
        streak_count = state.current_streak_count + 1
    else:
        streak_owner = winner_id
        streak_count = 1

    longest_owner = state.longest_streak_owner
    longest_count = state.longest_streak_count
    if streak_count > longest_count:
        longest_owner = streak_owner
        longest_count = streak_count

    # Activation window
    window_start = state.first_meeting_in_window_at
    if window_start is None:
        window_start = matched_at
    else:
        ws = window_start if window_start.tzinfo else window_start.replace(tzinfo=timezone.utc)
        if (matched_at - ws) > ACTIVATION_WINDOW:
            window_start = matched_at

    status = state.status
    activated_at = state.activated_at
    if status == "dormant":
        status = "tracking"
    if (
        status in ("tracking", "dormant")
        and meetings >= ACTIVATION_MEETINGS
        and window_start is not None
    ):
        ws = window_start if window_start.tzinfo else window_start.replace(tzinfo=timezone.utc)
        # Count meetings in window is approximated: if first-in-window + meetings>=3
        # and span ≤ 30d — for MVP require meetings>=3 and (matched_at - window_start) ≤ 30d
        if (matched_at - ws) <= ACTIVATION_WINDOW:
            status = "active"
            activated_at = matched_at
            if not was_active:
                events.append(
                    RivalryEvent(
                        code="rivalry_activated",
                        message="Third ranked meeting — rivalry activated.",
                    )
                )

    new_state = RivalryState(
        manager_a_id=a_id,
        manager_b_id=b_id,
        meetings=meetings,
        a_wins=a_wins,
        b_wins=b_wins,
        draws=draws,
        a_goals=state.a_goals + a_g,
        b_goals=state.b_goals + b_g,
        current_streak_owner=streak_owner,
        current_streak_count=streak_count,
        longest_streak_owner=longest_owner,
        longest_streak_count=longest_count,
        last_winner_id=winner_id,
        status=status,  # type: ignore[arg-type]
        activated_at=activated_at,
        last_match_at=matched_at,
        first_meeting_in_window_at=window_start,
    )

    # Narrative events (presentation only)
    if a_wins == b_wins and meetings >= 2 and (a_wins != prev_a_wins or b_wins != prev_b_wins or draws != state.draws):
        if winner_id is not None or draws > state.draws:
            if a_wins == b_wins:
                events.append(RivalryEvent(code="series_tied", message="Series tied."))

    prev_lead = _leader(prev_a_wins, prev_b_wins, a_id, b_id)
    new_lead = _leader(a_wins, b_wins, a_id, b_id)
    if prev_lead != new_lead and new_lead is not None:
        events.append(RivalryEvent(code="lead_changed", message="Head-to-head lead changed."))

    if streak_count == 3 and streak_owner is not None:
        events.append(
            RivalryEvent(code="three_win_streak", message="Three-match winning streak.")
        )

    if (
        prev_streak_owner is not None
        and prev_streak_count >= 3
        and winner_id is not None
        and winner_id != prev_streak_owner
    ):
        events.append(RivalryEvent(code="streak_broken", message="Winning streak broken."))
        events.append(RivalryEvent(code="revenge_served", message="Revenge win — streak ended."))

    if meetings == 5:
        events.append(RivalryEvent(code="fifth_meeting", message="Fifth ranked meeting."))
    if meetings == 10:
        events.append(RivalryEvent(code="tenth_meeting", message="Tenth ranked meeting."))

    return new_state, events


def _leader(a_wins: int, b_wins: int, a_id: int, b_id: int) -> int | None:
    if a_wins > b_wins:
        return a_id
    if b_wins > a_wins:
        return b_id
    return None


def badge_keys_earned(
    state: RivalryState,
    events: list[RivalryEvent],
    *,
    already: set[str] | None = None,
) -> list[str]:
    """Personal badge keys newly earned from this update (display only)."""
    already = already or set()
    earned: list[str] = []

    def add(key: str) -> None:
        if key not in already and key not in earned:
            earned.append(key)

    codes = {e.code for e in events}
    if "rivalry_activated" in codes:
        add("first_rival")
    if "revenge_served" in codes:
        add("revenge_served")
    if state.meetings >= 10:
        add("old_enemies")
    if state.meetings >= 10:
        lead = _leader(state.a_wins, state.b_wins, state.manager_a_id, state.manager_b_id)
        if lead is not None:
            add("rivalry_leader")
    if "streak_broken" in codes:
        add("streak_breaker")
    return earned
