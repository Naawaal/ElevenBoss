# packages/match_engine/match_engine/v3/possession.py
"""First-class Possession aggregate — flush / replay boundary."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Possession(BaseModel):
    owner: str  # home | away
    started_minute: int = 0
    ended_minute: int | None = None
    end_reason: str | None = None
    event_seq_start: int | None = None
    event_seq_end: int | None = None


class PossessionTracker:
    """Tracks open possession for boundary flush hints."""

    __slots__ = ("current", "_seq")

    def __init__(self) -> None:
        self.current: Possession | None = None
        self._seq = 0

    def start(self, owner: str, minute: int, seq: int) -> Possession:
        self.current = Possession(
            owner=owner, started_minute=minute, event_seq_start=seq
        )
        return self.current

    def end(self, minute: int, reason: str, seq: int) -> Possession | None:
        if self.current is None:
            return None
        self.current.ended_minute = minute
        self.current.end_reason = reason
        self.current.event_seq_end = seq
        ended = self.current
        self.current = None
        return ended
