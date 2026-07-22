# packages/match_engine/match_engine/v3/events.py
"""Versioned match events — sporting source of truth for NSS v3."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventCategory(str, Enum):
    SPORTING = "sporting"
    DECISION = "decision"
    ADMINISTRATIVE = "administrative"
    PROJECTION = "projection"


SPORTING_DIGEST_TYPES = frozenset({
    "KICKOFF",
    "HALF_TIME",
    "FULL_TIME",
    "GOAL",
    "SAVE",
    "MISS",
    "CHANCE",
    "FOUL",
    "YELLOW_CARD",
    "INJURY",
    "SUB_RESOLUTION",
    "TACTICAL_DECISION",
})

SCAFFOLDING_TYPES = frozenset({
    "POSSESSION_START",
    "POSSESSION_END",
    "PHASE_TRANSITION",
    "DECISION_WINDOW",
    "REPLAY_CHECKPOINT",
})


class MatchEventV3(BaseModel):
    seq: int = Field(..., ge=1)
    schema_version: int = 1
    engine_version: str = "nss_v3"
    minute: int = Field(..., ge=0, le=120)
    type: str
    category: EventCategory
    side: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    causal_hint: str | None = None

    def to_compat_dict(self) -> dict[str, Any]:
        p = self.payload
        out: dict[str, Any] = {
            "minute": self.minute,
            "type": self.type,
            "score_update": p.get("score_update", "0 - 0"),
            "actor": p.get("actor", ""),
            "team": p.get("team", ""),
        }
        if "assister" in p:
            out["assister"] = p["assister"]
        for k in (
            "interactive", "side", "injured_card_id", "injured_name", "injury_tier",
            "subs_remaining", "bench", "options", "gk_emergency",
        ):
            if k in p:
                out[k] = p[k]
        return out


def category_for_type(event_type: str) -> EventCategory:
    if event_type in ("TACTICAL_DECISION", "SUB_RESOLUTION"):
        return EventCategory.DECISION
    if event_type.startswith("PROJECTION_"):
        return EventCategory.PROJECTION
    if event_type in SCAFFOLDING_TYPES or event_type in (
        "KICKOFF", "HALF_TIME", "FULL_TIME", "DECISION_WINDOW", "REPLAY_CHECKPOINT",
    ):
        # KICKOFF/HT/FT are administrative but also sporting-digest members
        if event_type in ("KICKOFF", "HALF_TIME", "FULL_TIME"):
            return EventCategory.ADMINISTRATIVE
        return EventCategory.ADMINISTRATIVE
    return EventCategory.SPORTING


def from_compat_dict(
    raw: dict[str, Any],
    *,
    seq: int,
    engine_version: str = "nss_v3",
) -> MatchEventV3:
    et = str(raw.get("type") or "CHANCE")
    payload = {k: v for k, v in raw.items() if k not in ("minute", "type")}
    return MatchEventV3(
        seq=seq,
        minute=int(raw.get("minute") or 0),
        type=et,
        category=category_for_type(et),
        side=raw.get("side"),
        payload=payload,
        engine_version=engine_version,
    )
