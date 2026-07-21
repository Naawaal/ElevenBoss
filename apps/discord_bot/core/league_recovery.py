# apps/discord_bot/core/league_recovery.py
"""Stalled operation / catch-up recovery for League Lifecycle V1."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


async def recover_stalled_operations(db: Any, *, older_than_minutes: int = 30) -> int:
    """Mark stale starts failed; clear burned fixture resolve keys so wake-up can retry."""
    cleared = 0
    try:
        res = await db.table("league_operation_runs").select(
            "operation_key,started_at"
        ).eq("status", "started").execute()
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
        stale = [
            row["operation_key"] for row in (res.data or [])
            if _utc(row.get("started_at")) and _utc(row["started_at"]) < cutoff
        ]
        for key in stale:
            logger.error(
                "league_recovery stuck_operation operation_key=%s status=started "
                "older_than_minutes=%s — marking failed for retry",
                key,
                older_than_minutes,
            )
            await db.table("league_operation_runs").update({
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error": "stalled worker recovered; inspect before replay",
            }).eq("operation_key", key).execute()
        cleared += len(stale)
    except Exception:
        logger.exception("recover_stalled_operations failed")

    # Fixture resolve is retryable — delete failed leases for still-unplayed fixtures
    try:
        failed = await db.table("league_operation_runs").select("operation_key").eq(
            "status", "failed"
        ).execute()
        for row in failed.data or []:
            key = row.get("operation_key") or ""
            # Normative key: fixture:{uuid}:resolve
            if not key.startswith("fixture:") or not key.endswith(":resolve"):
                continue
            parts = key.split(":")
            if len(parts) < 3:
                continue
            fixture_id = parts[1]
            fx = await db.table("league_fixtures").select("id,is_played,status").eq(
                "id", fixture_id
            ).maybe_single().execute()
            data = fx.data or {}
            if data.get("is_played"):
                continue
            if data.get("status") not in ("failed_retryable", "running", "available", "scheduled", "locked", None):
                continue
            await db.table("league_operation_runs").delete().eq("operation_key", key).execute()
            cleared += 1
    except Exception:
        logger.exception("recover failed fixture resolve keys failed")
    return cleared


def _utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None
    return None


async def startup_recovery_pass(bot: Any, db: Any) -> None:
    """On bot start: catch up due V1 transitions then flush outbox."""
    from apps.discord_bot.core.league_lifecycle_engine import process_due_transitions
    from apps.discord_bot.core.league_outbox import publish_pending_outbox

    now = datetime.now(timezone.utc)
    try:
        await recover_stalled_operations(db)
        await process_due_transitions(bot, db, now)
    except Exception:
        logger.exception("startup_recovery_pass: process_due_transitions failed")
    try:
        await publish_pending_outbox(bot, db)
    except Exception:
        logger.exception("startup_recovery_pass: outbox flush failed")
