# packages/match_engine/match_engine/contracts/projector.py
from __future__ import annotations

from typing import Protocol

from match_engine.v3.events import MatchEventV3
from match_engine.v3.projectors import BoxScore, Explanation, ReplayTimeline


class BoxScoreProjector(Protocol):
    def __call__(self, events: list[MatchEventV3], **kwargs) -> BoxScore: ...


class ReplayProjector(Protocol):
    def __call__(self, events: list[MatchEventV3]) -> ReplayTimeline: ...


class ExplainabilityProjector(Protocol):
    def __call__(self, events: list[MatchEventV3], **kwargs) -> Explanation: ...
