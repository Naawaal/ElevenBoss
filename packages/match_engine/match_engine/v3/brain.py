# packages/match_engine/match_engine/v3/brain.py
"""BotBrain → Policy → DecisionIntent (AI never mutates MatchContext)."""
from __future__ import annotations

from typing import Protocol

from .context import DecisionContext
from .decisions import DecisionIntent


class Policy(Protocol):
    def propose(self, ctx: DecisionContext) -> DecisionIntent | None: ...


class DefaultPolicy:
    """Phase 0 — preserve today's non-interactive away behaviour (no mid-match tactics)."""

    def propose(self, ctx: DecisionContext) -> DecisionIntent | None:
        return None


class BotBrain:
    def __init__(self, policy: Policy | None = None) -> None:
        self.policy: Policy = policy or DefaultPolicy()

    def propose(self, ctx: DecisionContext) -> DecisionIntent | None:
        return self.policy.propose(ctx)
