# packages/match_engine/match_engine/contracts/decision.py
from __future__ import annotations

from typing import Protocol

from match_engine.v3.context import DecisionContext
from match_engine.v3.decisions import DecisionIntent


class PolicyProtocol(Protocol):
    def propose(self, ctx: DecisionContext) -> DecisionIntent | None: ...


class BotBrainProtocol(Protocol):
    def propose(self, ctx: DecisionContext) -> DecisionIntent | None: ...
