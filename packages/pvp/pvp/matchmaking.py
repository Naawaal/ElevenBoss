# packages/pvp/pvp/matchmaking.py
"""Guild-local Ranked PvP search widening, eligibility, and pair scoring."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pvp.models import PairScore, QueueCandidate, SearchRange

# Defaults mirror contracts/pvp-queue-rpcs.md / game_config
DEFAULT_INITIAL_LP = 100
DEFAULT_INITIAL_OVR = 4.0
DEFAULT_MAX_LP = 500
DEFAULT_MAX_OVR = 12.0
DEFAULT_SAME_PAIR_COOLDOWN = timedelta(minutes=30)
DEFAULT_SAME_PAIR_DAILY = 2
DEFAULT_MANAGER_DAILY = 5


def search_range_for_wait(
    wait_seconds: float,
    *,
    max_lp: int = DEFAULT_MAX_LP,
    max_ovr: float = DEFAULT_MAX_OVR,
) -> SearchRange:
    """Widen eligibility bands as queue age grows."""
    if wait_seconds < 15:
        return SearchRange(max_division_delta=0, max_lp_delta=DEFAULT_INITIAL_LP, max_ovr_delta=DEFAULT_INITIAL_OVR)
    if wait_seconds < 30:
        return SearchRange(max_division_delta=1, max_lp_delta=200, max_ovr_delta=7.0)
    if wait_seconds < 60:
        return SearchRange(max_division_delta=2, max_lp_delta=350, max_ovr_delta=10.0)
    return SearchRange(max_division_delta=99, max_lp_delta=max_lp, max_ovr_delta=max_ovr)


def wait_seconds(candidate: QueueCandidate, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    joined = candidate.joined_at
    if joined.tzinfo is None:
        joined = joined.replace(tzinfo=timezone.utc)
    return max(0.0, (now - joined).total_seconds())


def pair_in_range(
    a: QueueCandidate,
    b: QueueCandidate,
    band: SearchRange,
) -> bool:
    if a.owner_id == b.owner_id:
        return False
    if a.guild_id != b.guild_id:
        return False
    if abs(a.division_rank - b.division_rank) > band.max_division_delta:
        return False
    if abs(a.global_lp - b.global_lp) > band.max_lp_delta:
        return False
    if abs(a.xi_rating - b.xi_rating) > band.max_ovr_delta:
        return False
    return True


def score_pair(a: QueueCandidate, b: QueueCandidate, now: datetime | None = None) -> PairScore:
    now = now or datetime.now(timezone.utc)
    return PairScore(
        wait_seconds=min(wait_seconds(a, now), wait_seconds(b, now)),
        division_delta=abs(a.division_rank - b.division_rank),
        lp_delta=abs(a.global_lp - b.global_lp),
        ovr_delta=abs(a.xi_rating - b.xi_rating),
    )


def pair_blocked(
    owner_a: int,
    owner_b: int,
    blocks: set[tuple[int, int]],
) -> bool:
    """True if either direction is blocked. `blocks` is set of (blocker_id, blocked_id)."""
    return (owner_a, owner_b) in blocks or (owner_b, owner_a) in blocks


def pair_on_cooldown(
    last_ranked_at: datetime | None,
    *,
    now: datetime | None = None,
    cooldown: timedelta = DEFAULT_SAME_PAIR_COOLDOWN,
) -> bool:
    if last_ranked_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    ts = last_ranked_at if last_ranked_at.tzinfo else last_ranked_at.replace(tzinfo=timezone.utc)
    return (now - ts) < cooldown


def under_pair_daily_cap(pair_matches_today: int, *, cap: int = DEFAULT_SAME_PAIR_DAILY) -> bool:
    return pair_matches_today < cap


def under_manager_daily_cap(manager_matches_today: int, *, cap: int = DEFAULT_MANAGER_DAILY) -> bool:
    return manager_matches_today < cap


def eligible_pair(
    a: QueueCandidate,
    b: QueueCandidate,
    *,
    now: datetime | None = None,
    blocks: set[tuple[int, int]] | None = None,
    last_ranked_at: datetime | None = None,
    pair_matches_today: int = 0,
    a_matches_today: int = 0,
    b_matches_today: int = 0,
    max_lp: int = DEFAULT_MAX_LP,
    max_ovr: float = DEFAULT_MAX_OVR,
) -> bool:
    """Full MVP eligibility check for one candidate pair."""
    now = now or datetime.now(timezone.utc)
    if a.guild_id != b.guild_id or a.owner_id == b.owner_id:
        return False
    if blocks and pair_blocked(a.owner_id, b.owner_id, blocks):
        return False
    if pair_on_cooldown(last_ranked_at, now=now):
        return False
    if not under_pair_daily_cap(pair_matches_today):
        return False
    if not under_manager_daily_cap(a_matches_today) or not under_manager_daily_cap(b_matches_today):
        return False
    # Use the *stricter* (earlier) wait band so both are inside the older searcher's range
    band_a = search_range_for_wait(wait_seconds(a, now), max_lp=max_lp, max_ovr=max_ovr)
    band_b = search_range_for_wait(wait_seconds(b, now), max_lp=max_lp, max_ovr=max_ovr)
    # ponytail: require pair fits both managers' current widening bands
    return pair_in_range(a, b, band_a) and pair_in_range(a, b, band_b)


def best_opponent(
    seeker: QueueCandidate,
    others: list[QueueCandidate],
    *,
    now: datetime | None = None,
    blocks: set[tuple[int, int]] | None = None,
    pair_meta: dict[tuple[int, int], tuple[datetime | None, int]] | None = None,
    daily_counts: dict[int, int] | None = None,
) -> QueueCandidate | None:
    """Pick best eligible opponent for `seeker`. `pair_meta` keyed by canonical (min,max) ids."""
    now = now or datetime.now(timezone.utc)
    daily_counts = daily_counts or {}
    pair_meta = pair_meta or {}
    best: QueueCandidate | None = None
    best_key: tuple[float, int, int, float] | None = None
    for other in others:
        key = (min(seeker.owner_id, other.owner_id), max(seeker.owner_id, other.owner_id))
        last_at, pair_day = pair_meta.get(key, (None, 0))
        if not eligible_pair(
            seeker,
            other,
            now=now,
            blocks=blocks,
            last_ranked_at=last_at,
            pair_matches_today=pair_day,
            a_matches_today=daily_counts.get(seeker.owner_id, 0),
            b_matches_today=daily_counts.get(other.owner_id, 0),
        ):
            continue
        score = score_pair(seeker, other, now)
        sk = score.sort_key()
        if best_key is None or sk < best_key:
            best = other
            best_key = sk
    return best


def sorted_lock_order(owner_a: int, owner_b: int) -> tuple[int, int]:
    """Ascending discord IDs to avoid dual-lock deadlocks."""
    return (owner_a, owner_b) if owner_a < owner_b else (owner_b, owner_a)
