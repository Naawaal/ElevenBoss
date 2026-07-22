# apps/discord_bot/core/db_retry.py
"""Bounded retry for transient remote DB/API failures (US-43)."""
from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from apps.discord_bot.core import perf_signals

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ponytail: status-code sniffing via exception str — upgrade to typed httpx errors when client exposes them
_TRANSIENT_MARKERS = (
    "timeout",
    "timed out",
    "connection reset",
    "connection refused",
    "temporarily unavailable",
    "503",
    "502",
    "504",
    "429",
)


def is_transient_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    name = type(exc).__name__.lower()
    if "timeout" in name or "connection" in name:
        return True
    return any(m in text for m in _TRANSIENT_MARKERS)


async def with_db_retry(
    op: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay_s: float = 0.2,
    idempotent: bool = True,
    label: str = "db",
) -> T:
    """Retry ``op`` on transient failures when ``idempotent`` is True.

    Non-idempotent mutations must pass ``idempotent=False`` (no retry) unless
    the caller already holds an FR-006 idempotency key and the server is safe.
    """
    attempts = max(1, int(max_attempts))
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await op()
        except Exception as exc:
            last_exc = exc
            if not idempotent or not is_transient_error(exc) or attempt >= attempts:
                raise
            delay = base_delay_s * (2 ** (attempt - 1))
            delay *= 0.5 + random.random()  # jitter
            perf_signals.inc_retry()
            logger.warning(
                "perf.retry label=%s attempt=%s/%s delay=%.2fs err=%s",
                label,
                attempt,
                attempts,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc
