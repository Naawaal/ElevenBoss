# apps/discord_bot/core/perf_signals.py
"""In-process latency / cache / retry signals (US-43 FR-017)."""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from threading import Lock
from typing import Iterator

logger = logging.getLogger(__name__)

# Alert thresholds (contracts/observability-signals.md)
HUB_P95_LIGHT_MS = 2000
HUB_P95_BUSY_MS = 3000
CACHE_HIT_RATE_MIN = 0.70

_lock = Lock()
_hub_samples_ms: list[float] = []
_round_trips = 0
_retries = 0
_MAX_SAMPLES = 200


def inc_round_trip(n: int = 1) -> None:
    global _round_trips
    with _lock:
        _round_trips += n


def inc_retry(n: int = 1) -> None:
    global _retries
    with _lock:
        _retries += n


def record_hub(name: str, elapsed_ms: float, *, round_trips: int | None = None) -> None:
    with _lock:
        _hub_samples_ms.append(elapsed_ms)
        if len(_hub_samples_ms) > _MAX_SAMPLES:
            del _hub_samples_ms[: len(_hub_samples_ms) - _MAX_SAMPLES]
    extra = f" rts={round_trips}" if round_trips is not None else ""
    logger.info("perf.hub name=%s ms=%.1f%s", name, elapsed_ms, extra)


def snapshot() -> dict[str, float | int]:
    from apps.discord_bot.core import config_cache

    with _lock:
        samples = list(_hub_samples_ms)
        rts = _round_trips
        retries = _retries
    cache = config_cache.stats()
    total = cache["hits"] + cache["misses"]
    hit_rate = (cache["hits"] / total) if total else 0.0
    return {
        "hub_samples": len(samples),
        "hub_last_ms": samples[-1] if samples else 0.0,
        "round_trips": rts,
        "retries": retries,
        "cache_hits": cache["hits"],
        "cache_misses": cache["misses"],
        "cache_hit_rate": hit_rate,
    }


@contextmanager
def hub_timer(name: str) -> Iterator[dict[str, int]]:
    """Time a hub load; caller may set ``ctx['round_trips']`` before exit."""
    ctx: dict[str, int] = {}
    t0 = time.perf_counter()
    try:
        yield ctx
    finally:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        record_hub(name, elapsed_ms, round_trips=ctx.get("round_trips"))


def log_cache_stats() -> None:
    s = snapshot()
    logger.info(
        "perf.cache hits=%s misses=%s hit_rate=%.2f",
        s["cache_hits"],
        s["cache_misses"],
        s["cache_hit_rate"],
    )
