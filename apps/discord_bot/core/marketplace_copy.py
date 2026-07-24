"""Shared Marketplace UX copy (045) — one product language across hub + child views."""
from __future__ import annotations

PRODUCT_NAME = "Marketplace"
BACK_TO_MARKET = "Back to Market"
BACK_TO_LISTINGS = "Back to Listings"

# Shared session / ownership failures (managers see one voice)
OWNERSHIP_SESSION_ERROR = "This market session belongs to another manager."
OWNERSHIP_DASHBOARD_ERROR = "This dashboard is managed by another club."

SHOWING_UP_TO_25 = "Showing up to 25"


def hub_subtitle(*, transfer_enabled: bool) -> str:
    """Sub-areas under the Marketplace hub title."""
    parts = ["Transfer Board", "Scouting", "Agent"]
    if transfer_enabled:
        parts.append("My Listings")
    return " · ".join(parts)


def truncate_hint(total: int, *, cap: int = 25) -> str:
    if total > cap:
        return f"{SHOWING_UP_TO_25} of {total}"
    if total >= cap:
        return SHOWING_UP_TO_25
    return f"{total} listing(s)"
