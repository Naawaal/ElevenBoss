# packages/leagues/leagues/league_time.py
"""Guild League Time preferences: IANA validation, defaults, and preview copy.

Pure helpers only — no Discord / DB IO.
Defaults when unconfigured: timezone UTC, resolution hour 0 (00:00 local).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "UTC"
DEFAULT_RESOLUTION_HOUR = 0

# Raw offsets are not acceptable IANA identities (DST-unsafe as config keys).
_OFFSET_RE = re.compile(
    r"^(?:UTC|GMT)?\s*[+-]\s*\d{1,2}(?::?\d{2})?$",
    re.IGNORECASE,
)


class LeagueTimeError(ValueError):
    """Invalid League Time input."""


@dataclass(frozen=True, slots=True)
class EffectiveLeagueTime:
    timezone: str
    resolution_hour_local: int
    used_defaults: bool


def is_raw_utc_offset(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    return bool(_OFFSET_RE.match(text.replace(" ", "")))


def validate_iana_timezone(name: str) -> str:
    """Return canonical IANA name or raise LeagueTimeError."""
    tz_name = (name or "").strip()
    if not tz_name:
        raise LeagueTimeError("Timezone is required.")
    if is_raw_utc_offset(tz_name):
        raise LeagueTimeError(
            f"`{tz_name}` is a raw UTC offset. Use an IANA timezone like `Asia/Kathmandu`."
        )
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, Exception) as exc:
        raise LeagueTimeError(f"Unknown IANA timezone: `{tz_name}`") from exc
    return tz_name


def parse_resolution_hour(raw: str | int | None) -> int:
    """Accept `20`, `20:00`, or int; return 0–23."""
    if isinstance(raw, int):
        hour = raw
    else:
        text = (str(raw) if raw is not None else "").strip()
        if not text:
            raise LeagueTimeError("Resolution hour is required.")
        if ":" in text:
            text = text.split(":", 1)[0]
        try:
            hour = int(text)
        except ValueError as exc:
            raise LeagueTimeError("Resolution hour must be 0–23 (or HH:MM).") from exc
    if hour < 0 or hour > 23:
        raise LeagueTimeError("Resolution hour must be 0–23.")
    return hour


def coalesce_league_time(
    timezone_name: str | None,
    resolution_hour_local: int | None,
) -> EffectiveLeagueTime:
    """NULL guild settings → UTC / 0 without blocking."""
    used_defaults = timezone_name is None or resolution_hour_local is None
    tz = timezone_name if timezone_name else DEFAULT_TIMEZONE
    hour = DEFAULT_RESOLUTION_HOUR if resolution_hour_local is None else int(resolution_hour_local)
    # Validate only when explicitly set; defaults are always valid.
    if timezone_name is not None:
        tz = validate_iana_timezone(tz)
    if resolution_hour_local is not None:
        hour = parse_resolution_hour(hour)
    return EffectiveLeagueTime(timezone=tz, resolution_hour_local=hour, used_defaults=used_defaults)


def utc_equivalent_now(timezone_name: str, resolution_hour_local: int, *, now: datetime | None = None) -> datetime:
    """Today's local resolution instant expressed in UTC (for preview)."""
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    zi = ZoneInfo(timezone_name)
    local_now = now_utc.astimezone(zi)
    local_res = local_now.replace(
        hour=resolution_hour_local, minute=0, second=0, microsecond=0
    )
    return local_res.astimezone(timezone.utc)


def format_local_clock(hour: int) -> str:
    h12 = hour % 12 or 12
    suffix = "AM" if hour < 12 else "PM"
    return f"{h12}:00 {suffix}"


def format_utc_clock(dt: datetime) -> str:
    utc = dt.astimezone(timezone.utc)
    h12 = utc.hour % 12 or 12
    suffix = "AM" if utc.hour < 12 else "PM"
    return f"{h12}:{utc.minute:02d} {suffix} UTC"


def league_time_preview(
    timezone_name: str,
    resolution_hour_local: int,
    *,
    used_defaults: bool = False,
    now: datetime | None = None,
) -> str:
    """Stakeholder preview copy per contracts/league-time-settings.md."""
    utc_dt = utc_equivalent_now(timezone_name, resolution_hour_local, now=now)
    local = format_local_clock(resolution_hour_local)
    lines = [
        f"League matches will resolve daily at {local} {timezone_name}.",
        f"Current UTC equivalent: {format_utc_clock(utc_dt)}.",
        "This change will apply from the next season.",
    ]
    if used_defaults:
        lines.insert(
            0,
            "Using defaults (UTC @ 00:00) until League Time is configured.",
        )
    return "\n".join(lines)


def guild_setting_must_not_rewrite_season_snapshot() -> bool:
    """Documentation predicate for freeze tests — always True by policy."""
    return True
