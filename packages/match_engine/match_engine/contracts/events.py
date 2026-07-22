# packages/match_engine/match_engine/contracts/events.py
from __future__ import annotations

from typing import Protocol


class MatchEventProtocol(Protocol):
    seq: int
    type: str
    minute: int
    category: object
    payload: dict
