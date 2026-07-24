# packages/economy/economy/market_intelligence.py
"""Pure helpers for price discovery cohorts, trends, and transfer-board sorts (043)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

SORT_MODES: tuple[str, ...] = (
    "lowest_price",
    "highest_price",
    "highest_ovr",
    "highest_potential",
    "newest",
    "ending_soon",
    "best_value",
)

SORT_MODE_LABELS: dict[str, str] = {
    "lowest_price": "Lowest Price",
    "highest_price": "Highest Price",
    "highest_ovr": "Highest OVR",
    "highest_potential": "Highest Potential",
    "newest": "Newest",
    "ending_soon": "Ending Soon",
    "best_value": "Best Value",
}


def cohort_matches(
    *,
    subject_role: str,
    subject_rarity: str,
    subject_overall: int,
    sale_role: str | None,
    sale_rarity: str | None,
    sale_overall: int | None,
    ovr_window: int = 3,
) -> bool:
    """True when sale snapshot is complete and matches subject within OVR window."""
    if sale_role is None or sale_rarity is None or sale_overall is None:
        return False
    if sale_role != subject_role or sale_rarity != subject_rarity:
        return False
    return abs(int(sale_overall) - int(subject_overall)) <= int(ovr_window)


def insufficient_data(sample_size: int, min_sales: int = 5) -> bool:
    """True when cohort sample is below the configured minimum."""
    return int(sample_size) < int(min_sales)


def average_price(prices: list[int]) -> float | None:
    """Arithmetic mean of prices, or None if empty."""
    if not prices:
        return None
    return sum(prices) / len(prices)


def median_price(prices: list[int]) -> float | None:
    """Median of prices; even length averages the two middle values."""
    if not prices:
        return None
    ordered = sorted(prices)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def trend_from_medians(
    recent_median: float | None,
    prior_median: float | None,
) -> str | None:
    """Compare recent vs prior medians → up / down / flat, or None if either missing."""
    if recent_median is None or prior_median is None:
        return None
    if recent_median > prior_median:
        return "up"
    if recent_median < prior_median:
        return "down"
    return "flat"


def _player_card(row: dict[str, Any]) -> dict[str, Any]:
    pc = row.get("player_cards")
    if isinstance(pc, dict):
        return pc
    if isinstance(pc, list) and pc and isinstance(pc[0], dict):
        return pc[0]
    return {}


def _price_coins(row: dict[str, Any]) -> int:
    return int(row.get("price_coins") or 0)


def _overall(row: dict[str, Any]) -> int:
    return int(_player_card(row).get("overall") or 0)


def _potential(row: dict[str, Any]) -> int:
    return int(_player_card(row).get("potential") or 0)


def _best_value_key(
    row: dict[str, Any],
    fair_value_for_row: Callable[[dict[str, Any]], int | None] | None,
) -> tuple[int, float]:
    """(0, ratio) for valid fair; (1, …) sorts missing/non-positive fair last."""
    fair: int | None = None
    if fair_value_for_row is not None:
        fair = fair_value_for_row(row)
    if fair is None or fair <= 0:
        return (1, 0.0)
    return (0, _price_coins(row) / float(fair))


def sort_transfer_listings(
    rows: list[dict[str, Any]],
    mode: str,
    *,
    fair_value_for_row: Callable[[dict[str, Any]], int | None] | None = None,
) -> list[dict[str, Any]]:
    """Return a new list sorted by mode. Unknown mode → newest."""
    items = list(rows)
    key_mode = mode if mode in SORT_MODES else "newest"

    if key_mode == "lowest_price":
        return sorted(items, key=_price_coins)
    if key_mode == "highest_price":
        return sorted(items, key=_price_coins, reverse=True)
    if key_mode == "highest_ovr":
        return sorted(items, key=_overall, reverse=True)
    if key_mode == "highest_potential":
        return sorted(items, key=_potential, reverse=True)
    if key_mode == "ending_soon":
        # Missing expires_at sorts last (not ending soon).
        return sorted(
            items,
            key=lambda r: (r.get("expires_at") is None, r.get("expires_at") or ""),
        )
    if key_mode == "best_value":
        return sorted(items, key=lambda r: _best_value_key(r, fair_value_for_row))
    # newest (default)
    return sorted(items, key=lambda r: r.get("created_at") or "", reverse=True)


TREND_LABELS: dict[str, str] = {
    "up": "Rising",
    "down": "Softening",
    "flat": "Steady",
}


def format_relative_deadline(
    expires_at: Any,
    *,
    now: Any | None = None,
) -> str | None:
    """Human time-left from an expiry timestamp. None if missing/unparseable."""
    from datetime import datetime, timezone

    if expires_at is None:
        return None
    if now is None:
        now_dt = datetime.now(timezone.utc)
    elif getattr(now, "tzinfo", None) is None:
        now_dt = now.replace(tzinfo=timezone.utc)  # type: ignore[union-attr]
    else:
        now_dt = now  # type: ignore[assignment]

    if isinstance(expires_at, datetime):
        exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    else:
        text = str(expires_at).strip().replace("Z", "+00:00")
        try:
            exp = datetime.fromisoformat(text)
        except ValueError:
            return None
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)

    seconds = int((exp - now_dt).total_seconds())
    if seconds <= 0:
        return "Ending soon"
    hours = seconds // 3600
    if hours < 1:
        mins = max(1, seconds // 60)
        return f"{mins}m left" if mins < 60 else "Ending soon"
    if hours < 48:
        return f"{hours}h left" if hours > 2 else "Ending soon"
    days = hours // 24
    return f"{days}d left"


def trend_label(trend: str | None) -> str | None:
    """Map RPC trend token to manager-facing label."""
    if not trend:
        return None
    return TREND_LABELS.get(str(trend).lower().strip())


def ask_vs_fair_line(ask: int, fair: int | None) -> str:
    """Ask price with optional fair comparison — never invents fair."""
    ask_i = int(ask)
    if fair is None:
        return f"Ask **🪙 {ask_i:,}**"
    return f"Ask **🪙 {ask_i:,}** · Fair ~**🪙 {int(fair):,}**"


def format_discovery_presentation(discovery: dict[str, Any] | None, *, compact: bool = False) -> str:
    """Manager-readable discovery body from RPC payload only."""
    if not discovery:
        return "*Market data unavailable right now.*"
    active = int(discovery.get("active_count") or 0)
    low = discovery.get("lowest_active")
    high = discovery.get("highest_active")
    active_line = f"Active similar listings: **{active}**"
    if active and low is not None and high is not None:
        active_line += f" · 🪙 {int(low):,} – {int(high):,}"
    if discovery.get("insufficient_data"):
        return (
            "Not enough recent sales for similar players yet "
            f"(need {discovery.get('min_sales', 5)}; have {discovery.get('sample_size', 0)}).\n"
            f"{active_line}"
        )
    label = trend_label(discovery.get("trend") if isinstance(discovery.get("trend"), str) else None)
    trend_line = f"\nTrend (7d vs prior): **{label}**" if label else ""
    body = (
        f"Similar sales — avg **🪙 {int(discovery.get('avg_sale_price', 0)):,}** · "
        f"median **🪙 {int(discovery.get('median_sale_price', 0)):,}** "
        f"(n={discovery.get('sample_size', 0)})\n"
        f"{active_line}{trend_line}"
    )
    if compact:
        fair_hint = ""
        if discovery.get("median_sale_price") is not None:
            fair_hint = f" · median 🪙 {int(discovery['median_sale_price']):,}"
        compact_trend = f" · {label}" if label else ""
        return f"Market{fair_hint}{compact_trend} · {active} similar listed"
    recent = discovery.get("recent_sales")
    if isinstance(recent, list) and recent:
        prices: list[str] = []
        for item in recent[:3]:
            if isinstance(item, dict) and item.get("price_coins") is not None:
                prices.append(f"🪙 {int(item['price_coins']):,}")
            elif isinstance(item, (int, float)):
                prices.append(f"🪙 {int(item):,}")
        if prices:
            body += f"\nRecent: {' · '.join(prices)}"
    return body
