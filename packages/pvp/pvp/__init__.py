# packages/pvp/pvp/__init__.py
"""Pure Ranked PvP matchmaking, rivalry math, and reward policy (Feature 053)."""
from __future__ import annotations

from pvp.matchmaking import (
    best_opponent,
    eligible_pair,
    pair_blocked,
    score_pair,
    search_range_for_wait,
    sorted_lock_order,
    wait_seconds,
)
from pvp.models import (
    PairScore,
    QueueCandidate,
    RewardPolicyResult,
    RivalryEvent,
    RivalryState,
    SearchRange,
)
from pvp.reward_policy import (
    assert_lp_allowed,
    practice_lp_delta,
    pvp_lp_delta,
    reward_policy,
)
from pvp.rivalry_math import (
    apply_ranked_meeting,
    badge_keys_earned,
    canonical_pair,
    refresh_dormancy,
)

__all__ = [
    "PairScore",
    "QueueCandidate",
    "RewardPolicyResult",
    "RivalryEvent",
    "RivalryState",
    "SearchRange",
    "apply_ranked_meeting",
    "assert_lp_allowed",
    "badge_keys_earned",
    "best_opponent",
    "canonical_pair",
    "eligible_pair",
    "pair_blocked",
    "practice_lp_delta",
    "pvp_lp_delta",
    "refresh_dormancy",
    "reward_policy",
    "score_pair",
    "search_range_for_wait",
    "sorted_lock_order",
    "wait_seconds",
]
