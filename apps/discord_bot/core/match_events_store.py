# apps/discord_bot/core/match_events_store.py
"""Append-only match_events flush helpers (possession-boundary batches)."""
from __future__ import annotations

from typing import Any

from match_engine.v3.events import MatchEventV3


def events_to_rows(run_id: str, events: list[MatchEventV3]) -> list[dict[str, Any]]:
    return [
        {
            "run_id": run_id,
            "seq": ev.seq,
            "schema_version": ev.schema_version,
            "engine_version": ev.engine_version,
            "minute": ev.minute,
            "event_type": ev.type,
            "side": ev.side,
            "payload": ev.payload,
            "causal_hint": ev.causal_hint,
        }
        for ev in events
    ]


async def append_match_events(
    db: Any,
    run_id: str,
    events: list[MatchEventV3],
    *,
    flushed_thru: int,
) -> int:
    """
    Insert events with seq > flushed_thru. Idempotent on (run_id, seq).
    Returns new events_flushed_thru.
    """
    batch = [e for e in events if e.seq > flushed_thru]
    if not batch:
        return flushed_thru
    rows = events_to_rows(run_id, batch)
    # Upsert-like: ignore conflicts if client retries
    try:
        await db.table("match_events").upsert(rows, on_conflict="run_id,seq").execute()
    except Exception:
        # Fallback: insert one-by-one skipping duplicates
        for row in rows:
            try:
                await db.table("match_events").insert(row).execute()
            except Exception:
                continue
    new_thru = max(e.seq for e in batch)
    await db.table("match_runs").update({"events_flushed_thru": new_thru}).eq("id", run_id).execute()
    return new_thru


async def load_run_decision_intents(db: Any, run_id: str) -> list:
    """Load TACTICAL_DECISION events for recovery replay (T058)."""
    from match_engine.v3.decisions import intents_from_decision_events

    res = (
        await db.table("match_events")
        .select("event_type,minute,side,payload,seq")
        .eq("run_id", run_id)
        .eq("event_type", "TACTICAL_DECISION")
        .order("seq")
        .execute()
    )
    return intents_from_decision_events(res.data or [])
