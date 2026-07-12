# packages/player_engine/player_engine/bench_rest.py
"""Pure bench-rest candidate selection (competitive matches)."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

BENCH_REST_LIMIT = 7


def pick_bench_rest_ids(
    cards: Sequence[Mapping[str, Any]],
    starter_ids: Sequence[str],
    *,
    limit: int = BENCH_REST_LIMIT,
) -> list[str]:
    """
    Unused healthy non-retired cards eligible for post-match bench rest.

    Ordered by overall DESC, then id ASC; capped at ``limit`` (default 7).
    """
    starter_set = {str(i) for i in starter_ids}
    candidates: list[tuple[int, str, str]] = []
    for row in cards:
        cid = str(row.get("id") or "")
        if not cid or cid in starter_set:
            continue
        if row.get("is_retired"):
            continue
        if row.get("injury_tier") is not None:
            continue
        overall = int(row.get("overall") or 0)
        candidates.append((overall, cid, cid))
    candidates.sort(key=lambda t: (-t[0], t[1]))
    return [cid for _, cid, _ in candidates[: max(0, limit)]]
