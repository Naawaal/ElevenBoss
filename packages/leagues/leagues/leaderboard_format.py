# packages/leagues/leagues/leaderboard_format.py
"""Pure formatting helpers for /leaderboard embeds (US-30)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .calculator import compute_promotions_relegations
from .models import LeagueEntry


def weekly_reset_countdown(now_utc: datetime | None = None) -> str:
    """Human-readable time until next Monday 00:00 UTC."""
    now = now_utc or datetime.now(timezone.utc)
    days_ahead = (7 - now.weekday()) % 7
    next_mon = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
    if next_mon <= now:
        next_mon += timedelta(days=7)
    delta = next_mon - now
    days = delta.days
    hours = delta.seconds // 3600
    mins = (delta.seconds % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def promotion_zone_labels(n: int) -> tuple[str, str]:
    """Return (promotion_range, relegation_range) as '#1–#N' strings."""
    if n == 0:
        return "—", "—"
    entries = [LeagueEntry(discord_id=i, league_points=0, goal_difference=0) for i in range(n)]
    res = compute_promotions_relegations(entries)
    num_promo = len(res.promoted_ids)
    num_releg = len(res.relegated_ids)
    promo = f"#1–#{num_promo}" if num_promo else "—"
    releg = f"#{n - num_releg + 1}–#{n}" if num_releg else "—"
    return promo, releg


def zone_suffix(position: int, n: int, promoted_count: int, relegated_count: int) -> str:
    if n == 0:
        return ""
    if position <= promoted_count:
        return " ↑"
    if position > n - relegated_count:
        return " ↓"
    return ""


def format_rank_line(
    position: int,
    club_name: str,
    pts: int,
    gd: int,
    viewer_id: int,
    row_discord_id: int,
    zone: str = "",
    extra: str = "",
) -> str:
    marker = "▶ " if row_discord_id == viewer_id else "  "
    gd_str = f"+{gd}" if gd >= 0 else str(gd)
    name = (club_name or "?")[:18]
    return f"{marker}#{position}  {name:<18} {pts:>3} pts  GD {gd_str}{zone}{extra}"


def paginate_rows(rows: list, page: int, per_page: int = 10) -> tuple[list, int, int]:
    """Return (page_rows, total_pages, clamped_page)."""
    if not rows:
        return [], 1, 0
    total_pages = max(1, (len(rows) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    return rows[start : start + per_page], total_pages, page


def viewer_page_index(viewer_rank: int, per_page: int = 10) -> int:
    """0-based page containing viewer rank (1-based rank)."""
    if viewer_rank <= 0:
        return 0
    return (viewer_rank - 1) // per_page
