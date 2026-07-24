# tests/test_marketplace_ux_polish.py
"""Presentation helpers for Marketplace V1.5 UX polish (045)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from economy import (
    ask_vs_fair_line,
    format_discovery_presentation,
    format_relative_deadline,
    trend_label,
)


def test_format_relative_deadline_hours_and_ending_soon():
    now = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)
    assert format_relative_deadline(now + timedelta(hours=14), now=now) == "14h left"
    assert format_relative_deadline(now + timedelta(minutes=30), now=now) == "30m left"
    assert format_relative_deadline(now + timedelta(hours=1), now=now) == "Ending soon"
    assert format_relative_deadline(now - timedelta(minutes=5), now=now) == "Ending soon"
    assert format_relative_deadline(None, now=now) is None


def test_trend_label_mapping():
    assert trend_label("up") == "Rising"
    assert trend_label("down") == "Softening"
    assert trend_label("flat") == "Steady"
    assert trend_label(None) is None
    assert trend_label("nope") is None


def test_ask_vs_fair_omits_when_null():
    assert ask_vs_fair_line(2400, None) == "Ask **🪙 2,400**"
    assert "Fair" in ask_vs_fair_line(2400, 2100)
    assert "2,100" in ask_vs_fair_line(2400, 2100)


def test_discovery_insufficient_invents_nothing():
    text = format_discovery_presentation(
        {"insufficient_data": True, "min_sales": 5, "sample_size": 2, "active_count": 1}
    )
    assert "Not enough" in text
    assert "Similar sales" not in text
    assert "avg" not in text

def test_discovery_with_recent_sales_and_trend():
    text = format_discovery_presentation(
        {
            "avg_sale_price": 2200,
            "median_sale_price": 2100,
            "sample_size": 8,
            "active_count": 3,
            "lowest_active": 1900,
            "highest_active": 2500,
            "trend": "down",
            "recent_sales": [{"price_coins": 2300}, {"price_coins": 2100}, {"price_coins": 2400}],
        }
    )
    assert "Softening" in text
    assert "Recent:" in text
    assert "2,300" in text


def test_discovery_compact():
    text = format_discovery_presentation(
        {
            "avg_sale_price": 2200,
            "median_sale_price": 2100,
            "sample_size": 8,
            "active_count": 3,
            "trend": "up",
        },
        compact=True,
    )
    assert "Rising" in text
    assert "Recent:" not in text
