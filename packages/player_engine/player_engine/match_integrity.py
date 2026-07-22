# packages/player_engine/player_engine/match_integrity.py
"""Pure match-run recovery classification (US-42.4)."""
from __future__ import annotations

from typing import Literal

RecoveryAction = Literal["complete", "abandon", "noop"]

_TERMINAL = frozenset({"completed", "abandoned", "failed"})
_INTERRUPTED = frozenset({"streaming", "completing"})


def classify_interrupted_run(*, status: str, rewards_applied: bool) -> RecoveryAction:
    """Decide boot/recovery action for a match run.

    - Already terminal → noop
    - Interrupted + rewards already durable → complete (never abandon-after-pay)
    - Interrupted + no rewards → abandon
    """
    s = (status or "").strip().lower()
    if s in _TERMINAL:
        return "noop"
    if s not in _INTERRUPTED:
        return "noop"
    if rewards_applied:
        return "complete"
    return "abandon"
