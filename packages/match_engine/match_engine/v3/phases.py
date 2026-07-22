# packages/match_engine/match_engine/v3/phases.py
"""Phase constants — sporting loop lives in v2 generate_match_events for Phase 0 parity."""
from __future__ import annotations

# Re-export Phase enum from v2 for adapters
from match_engine.v2_simulator import Phase, _STAT_DIFF_DIVISOR, _probability_floor

__all__ = ["Phase", "_STAT_DIFF_DIVISOR", "_probability_floor"]
