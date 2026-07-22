# packages/match_engine/match_engine/contracts/simulation.py
from __future__ import annotations

from typing import Protocol

from match_engine.v3.context import MatchContext, StepResult
from match_engine.v3.decisions import DecisionInbox


class SimulationEngineProtocol(Protocol):
    def initial_context(self, **kwargs) -> MatchContext: ...

    def step(
        self, context: MatchContext, inbox: DecisionInbox | None = None
    ) -> StepResult: ...

    def run_to_completion(
        self, context: MatchContext, **kwargs
    ) -> tuple[MatchContext, list]: ...
