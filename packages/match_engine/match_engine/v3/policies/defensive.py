# packages/match_engine/match_engine/v3/policies/defensive.py
from __future__ import annotations

from match_engine.v3.context import DecisionContext
from match_engine.v3.decisions import DecisionIntent


class DefensivePolicy:
    """Wave 3 — sit deep when leading late; never mutates context."""

    def propose(self, ctx: DecisionContext) -> DecisionIntent | None:
        away_leading = ctx.away_score > ctx.home_score
        if away_leading and ctx.minute >= 70 and ctx.own_tactic != "defend":
            return DecisionIntent(
                side="away",
                kind="set_tactic",
                payload={"tactic": "defend"},
                requested_at_minute=ctx.minute,
                source="ai",
            )
        return None
