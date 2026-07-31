# apps/discord_bot/core/perf_signals.py
"""In-process latency / cache / retry signals (US-43 + 050 observability)."""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from threading import Lock
from typing import Any, Iterator

logger = logging.getLogger(__name__)

HUB_P95_LIGHT_MS = 2000
HUB_P95_BUSY_MS = 3000
CACHE_HIT_RATE_MIN = 0.70
_MAX_SAMPLES = 200
_BUCKET_TTL_S = 60.0

_lock = Lock()
_hub_samples_ms: list[float] = []
_round_trips = 0
_retries = 0
_status_429 = 0
_status_5xx = 0
# hub -> list of recent ms samples
_hub_named: dict[str, list[float]] = defaultdict(list)
_hub_counts: dict[str, int] = defaultdict(int)
_hub_errors: dict[str, int] = defaultdict(int)
_last_flush_mono = time.monotonic()


def _percentile(sorted_samples: list[float], p: float) -> float:
    if not sorted_samples:
        return 0.0
    if len(sorted_samples) == 1:
        return sorted_samples[0]
    k = (len(sorted_samples) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_samples) - 1)
    if f == c:
        return sorted_samples[f]
    return sorted_samples[f] + (sorted_samples[c] - sorted_samples[f]) * (k - f)


def inc_round_trip(n: int = 1) -> None:
    global _round_trips
    with _lock:
        _round_trips += n


def inc_retry(n: int = 1) -> None:
    global _retries
    with _lock:
        _retries += n


def inc_status(code: int) -> None:
    global _status_429, _status_5xx
    with _lock:
        if code == 429:
            _status_429 += 1
        elif 500 <= code <= 599:
            _status_5xx += 1


def record_hub(
    name: str,
    elapsed_ms: float,
    *,
    round_trips: int | None = None,
    error: bool = False,
) -> None:
    with _lock:
        _hub_samples_ms.append(elapsed_ms)
        if len(_hub_samples_ms) > _MAX_SAMPLES:
            del _hub_samples_ms[: len(_hub_samples_ms) - _MAX_SAMPLES]
        samples = _hub_named[name]
        samples.append(elapsed_ms)
        if len(samples) > _MAX_SAMPLES:
            del samples[: len(samples) - _MAX_SAMPLES]
        _hub_counts[name] += 1
        if error:
            _hub_errors[name] += 1
    extra = f" rts={round_trips}" if round_trips is not None else ""
    logger.info("perf.hub name=%s ms=%.1f%s", name, elapsed_ms, extra)
    _maybe_flush()


def _hub_stats(name: str, samples: list[float]) -> dict[str, Any]:
    ordered = sorted(samples)
    return {
        "count": _hub_counts.get(name, 0),
        "errors": _hub_errors.get(name, 0),
        "p50_ms": round(_percentile(ordered, 50), 1),
        "p95_ms": round(_percentile(ordered, 95), 1),
        "p99_ms": round(_percentile(ordered, 99), 1),
        "last_ms": round(samples[-1], 1) if samples else 0.0,
    }


def snapshot() -> dict[str, Any]:
    from apps.discord_bot.core import config_cache
    from apps.discord_bot.core.instance_id import get_instance_id

    with _lock:
        samples = list(_hub_samples_ms)
        rts = _round_trips
        retries = _retries
        s429 = _status_429
        s5xx = _status_5xx
        named = {k: list(v) for k, v in _hub_named.items()}
        counts = dict(_hub_counts)
        errors = dict(_hub_errors)
    cache = config_cache.stats()
    total = cache["hits"] + cache["misses"]
    hit_rate = (cache["hits"] / total) if total else 0.0
    hubs = {
        name: {
            **_hub_stats(name, named.get(name, [])),
            "count": counts.get(name, 0),
            "errors": errors.get(name, 0),
        }
        for name in sorted(set(counts) | set(named))
    }
    ordered = sorted(samples)
    return {
        "instance_id": get_instance_id(),
        "hub_samples": len(samples),
        "hub_last_ms": samples[-1] if samples else 0.0,
        "hub_p50_ms": round(_percentile(ordered, 50), 1),
        "hub_p95_ms": round(_percentile(ordered, 95), 1),
        "hub_p99_ms": round(_percentile(ordered, 99), 1),
        "round_trips": rts,
        "retries": retries,
        "status_429": s429,
        "status_5xx": s5xx,
        "cache_hits": cache["hits"],
        "cache_misses": cache["misses"],
        "cache_hit_rate": hit_rate,
        "cache_entries": cache.get("size", cache.get("entries", 0)),
        "hubs": hubs,
        "uptime_hint": "process-local counters (reset on restart)",
    }


def _maybe_flush() -> None:
    global _last_flush_mono
    now = time.monotonic()
    with _lock:
        if now - _last_flush_mono < _BUCKET_TTL_S:
            return
        _last_flush_mono = now
    s = snapshot()
    logger.info(
        "perf.flush instance=%s p50=%.1f p95=%.1f p99=%.1f rts=%s retries=%s "
        "429=%s 5xx=%s cache_hit=%.2f hubs=%s",
        s["instance_id"],
        s["hub_p50_ms"],
        s["hub_p95_ms"],
        s["hub_p99_ms"],
        s["round_trips"],
        s["retries"],
        s["status_429"],
        s["status_5xx"],
        s["cache_hit_rate"],
        len(s["hubs"]),
    )


@contextmanager
def hub_timer(name: str) -> Iterator[dict[str, int]]:
    """Time a hub load; caller may set ``ctx['round_trips']`` before exit."""
    ctx: dict[str, int] = {}
    t0 = time.perf_counter()
    err = False
    try:
        yield ctx
    except Exception:
        err = True
        raise
    finally:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        record_hub(name, elapsed_ms, round_trips=ctx.get("round_trips"), error=err)


def log_cache_stats() -> None:
    s = snapshot()
    logger.info(
        "perf.cache hits=%s misses=%s hit_rate=%.2f",
        s["cache_hits"],
        s["cache_misses"],
        s["cache_hit_rate"],
    )


def format_admin_embed_fields(s: dict[str, Any] | None = None) -> list[tuple[str, str]]:
    """Field pairs for owner-only Performance panel."""
    snap = s or snapshot()
    lines = [
        f"instance `{snap['instance_id']}`",
        f"p50/p95/p99 **{snap['hub_p50_ms']:.0f}** / **{snap['hub_p95_ms']:.0f}** / "
        f"**{snap['hub_p99_ms']:.0f}** ms",
        f"round_trips `{snap['round_trips']}` · retries `{snap['retries']}`",
        f"429 `{snap['status_429']}` · 5xx `{snap['status_5xx']}`",
        f"cache hit **{snap['cache_hit_rate']:.0%}** "
        f"({snap['cache_hits']}/{snap['cache_hits'] + snap['cache_misses']}) "
        f"entries `{snap.get('cache_entries', 0)}`",
    ]
    hubs = snap.get("hubs") or {}
    if hubs:
        top = sorted(hubs.items(), key=lambda kv: kv[1].get("count", 0), reverse=True)[:8]
        hub_lines = [
            f"`{name}` n={h['count']} p95={h['p95_ms']:.0f}ms"
            for name, h in top
        ]
        lines.append("hubs: " + " · ".join(hub_lines))
    return [("Performance", "\n".join(lines))]
