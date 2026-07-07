# tests/test_leaderboard_format.py
from datetime import datetime, timezone

from leagues import (
    format_rank_line,
    paginate_rows,
    promotion_zone_labels,
    viewer_page_index,
    weekly_reset_countdown,
    zone_suffix,
)


def test_weekly_reset_countdown_future() -> None:
    # Tuesday 2026-07-07 12:00 UTC -> next Monday in ~5d
    now = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)
    s = weekly_reset_countdown(now)
    assert "d" in s or "h" in s


def test_paginate_rows() -> None:
    rows = list(range(25))
    page_rows, total, page = paginate_rows(rows, 0, per_page=10)
    assert len(page_rows) == 10
    assert total == 3
    assert page == 0


def test_viewer_page_index() -> None:
    assert viewer_page_index(1) == 0
    assert viewer_page_index(11) == 1


def test_format_rank_line_highlights_viewer() -> None:
    line = format_rank_line(1, "Test FC", 9, 4, viewer_id=42, row_discord_id=42)
    assert line.startswith("▶")


def test_promotion_zone_labels() -> None:
    promo, releg = promotion_zone_labels(10)
    assert promo.startswith("#1")
    assert releg.startswith("#")


def test_zone_suffix() -> None:
    assert zone_suffix(1, 10, 2, 2) == " ↑"
    assert zone_suffix(10, 10, 2, 2) == " ↓"
    assert zone_suffix(5, 10, 2, 2) == ""
