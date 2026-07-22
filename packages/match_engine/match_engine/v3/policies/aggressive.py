# packages/match_engine/match_engine/v3/policies/aggressive.py
from __future__ import annotations

from match_engine.v3.context import DecisionContext
from match_engine.v3.decisions import DecisionIntent


class AggressivePolicy:
    """Wave 3 — push Attack when trailing late; never mutates context."""

    def propose(self, ctx: DecisionContext) -> DecisionIntent | None:
        if ctx.trailing and ctx.minute >= 60 and ctx.own_tactic != "attack":
            return DecisionIntent(
                side="away",
                kind="set_tactic",
                payload={"tactic": "attack"},
                requested_at_minute=ctx.minute,
                source="ai",
            )
        return None
