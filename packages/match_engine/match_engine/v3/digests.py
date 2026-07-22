# packages/match_engine/match_engine/v3/digests.py
"""Three formal digests — Sporting, Deterministic Replay, Settlement (FR-021)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .events import (
    EventCategory,
    MatchEventV3,
    SCAFFOLDING_TYPES,
    SPORTING_DIGEST_TYPES,
)


DIGEST_RECIPE_VERSION = 1


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sporting_digest(
    events: list[MatchEventV3],
    *,
    home_score: int,
    away_score: int,
) -> str:
    """Cross-version gameplay compare (excludes scaffolding / projection)."""
    rows = []
    for ev in events:
        if ev.category == EventCategory.PROJECTION:
            continue
        if ev.type in SCAFFOLDING_TYPES:
            continue
        if ev.type not in SPORTING_DIGEST_TYPES and ev.category not in (
            EventCategory.SPORTING,
            EventCategory.DECISION,
            EventCategory.ADMINISTRATIVE,
        ):
            continue
        if ev.type in SPORTING_DIGEST_TYPES or ev.type in (
            "KICKOFF", "HALF_TIME", "FULL_TIME", "TACTICAL_DECISION", "SUB_RESOLUTION",
        ):
            rows.append({
                "seq": ev.seq,
                "minute": ev.minute,
                "type": ev.type,
                "side": ev.side,
                "payload": {
                    k: ev.payload.get(k)
                    for k in (
                        "actor", "assister", "team", "score_update",
                        "injured_card_id", "injury_tier", "tactic", "style",
                        "kind", "replacement_card_id", "play_on",
                    )
                    if k in ev.payload
                },
            })
    body = {
        "recipe": DIGEST_RECIPE_VERSION,
        "home_score": home_score,
        "away_score": away_score,
        "events": rows,
    }
    return _sha(_canonical(body))


def deterministic_replay_digest(events: list[MatchEventV3]) -> str:
    """v3↔v3 full deterministic stream including scaffolding."""
    rows = []
    for ev in events:
        if ev.category == EventCategory.PROJECTION:
            continue
        rows.append({
            "seq": ev.seq,
            "minute": ev.minute,
            "type": ev.type,
            "category": ev.category.value,
            "side": ev.side,
            "payload": ev.payload,
            "causal_hint": ev.causal_hint,
            "schema_version": ev.schema_version,
            "engine_version": ev.engine_version,
        })
    return _sha(_canonical({"recipe": DIGEST_RECIPE_VERSION, "events": rows}))


def settlement_digest(payload: dict[str, Any]) -> str:
    """
    Integrity digest over settlement-relevant fields.
    Caller supplies coins/XP/fatigue/injuries/LP/history/idempotency keys.
    """
    return _sha(_canonical({"recipe": DIGEST_RECIPE_VERSION, "settlement": payload}))
