# apps/discord_bot/core/idempotent_outcome.py
"""FR-006a Idempotent Outcome parser (US-43)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

OutcomeStatus = Literal["applied", "already_applied", "rejected"]


class IdempotentOutcome(BaseModel):
    status: OutcomeStatus
    reason: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


def parse_idempotent_outcome(raw: dict[str, Any] | None) -> IdempotentOutcome:
    """Normalize RPC JSON to FR-006a envelope.

    Maps legacy economy ``replay: true`` → ``already_applied``.
    """
    body = dict(raw or {})
    status_raw = body.get("status")
    if status_raw in ("applied", "already_applied", "rejected"):
        data = body.get("data")
        if not isinstance(data, dict):
            data = {k: v for k, v in body.items() if k not in ("status", "reason", "data")}
        return IdempotentOutcome(
            status=status_raw,  # type: ignore[arg-type]
            reason=body.get("reason") if isinstance(body.get("reason"), str) else None,
            data=data,
        )

    if body.get("replay") is True or body.get("already_applied") is True:
        data = {k: v for k, v in body.items() if k not in ("replay", "already_applied", "status", "reason")}
        return IdempotentOutcome(status="already_applied", data=data)

    if body.get("ok") is False or body.get("error") or body.get("rejected") is True:
        reason = body.get("reason") or body.get("error") or body.get("message")
        return IdempotentOutcome(
            status="rejected",
            reason=str(reason) if reason is not None else "rejected",
            data={k: v for k, v in body.items() if k not in ("ok", "error", "rejected", "reason", "message")},
        )

    # Default success without explicit status
    data = {k: v for k, v in body.items() if k not in ("replay", "status", "reason")}
    return IdempotentOutcome(status="applied", data=data)
