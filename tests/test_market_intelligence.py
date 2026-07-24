# tests/test_market_intelligence.py
"""043 market intelligence pure-helper checks."""
from __future__ import annotations

from economy.market_intelligence import (
    SORT_MODE_LABELS,
    SORT_MODES,
    average_price,
    cohort_matches,
    insufficient_data,
    median_price,
    sort_transfer_listings,
    trend_from_medians,
)


def test_cohort_matches_window_and_nulls():
    assert cohort_matches(
        subject_role="MID",
        subject_rarity="Rare",
        subject_overall=78,
        sale_role="MID",
        sale_rarity="Rare",
        sale_overall=80,
        ovr_window=3,
    )
    assert not cohort_matches(
        subject_role="MID",
        subject_rarity="Rare",
        subject_overall=78,
        sale_role="MID",
        sale_rarity="Rare",
        sale_overall=82,
        ovr_window=3,
    )
    assert not cohort_matches(
        subject_role="MID",
        subject_rarity="Rare",
        subject_overall=78,
        sale_role=None,
        sale_rarity="Rare",
        sale_overall=78,
    )
    assert not cohort_matches(
        subject_role="MID",
        subject_rarity="Rare",
        subject_overall=78,
        sale_role="mid",
        sale_rarity="Rare",
        sale_overall=78,
    )


def test_insufficient_data_default_min_five():
    assert insufficient_data(4) is True
    assert insufficient_data(5) is False
    assert insufficient_data(3, min_sales=3) is False


def test_average_and_median():
    assert average_price([]) is None
    assert average_price([100, 200, 300]) == 200.0
    assert median_price([]) is None
    assert median_price([10, 30, 20]) == 20.0
    assert median_price([10, 40, 20, 30]) == 25.0


def test_trend_from_medians():
    assert trend_from_medians(200.0, 150.0) == "up"
    assert trend_from_medians(100.0, 150.0) == "down"
    assert trend_from_medians(120.0, 120.0) == "flat"
    assert trend_from_medians(None, 100.0) is None
    assert trend_from_medians(100.0, None) is None


def _fixture_rows() -> list[dict]:
    return [
        {
            "id": "a",
            "price_coins": 3000,
            "created_at": "2026-07-01T12:00:00+00:00",
            "expires_at": "2026-07-10T12:00:00+00:00",
            "player_cards": {"overall": 70, "potential": 80, "rarity": "Rare"},
        },
        {
            "id": "b",
            "price_coins": 1000,
            "created_at": "2026-07-03T12:00:00+00:00",
            "expires_at": "2026-07-05T12:00:00+00:00",
            "player_cards": {"overall": 85, "potential": 88, "rarity": "Epic"},
        },
        {
            "id": "c",
            "price_coins": 2000,
            "created_at": "2026-07-02T12:00:00+00:00",
            "expires_at": "2026-07-08T12:00:00+00:00",
            "player_cards": {"overall": 78, "potential": 92, "rarity": "Rare"},
        },
    ]


def test_sort_all_seven_modes():
    rows = _fixture_rows()
    assert [r["id"] for r in sort_transfer_listings(rows, "lowest_price")] == ["b", "c", "a"]
    assert [r["id"] for r in sort_transfer_listings(rows, "highest_price")] == ["a", "c", "b"]
    assert [r["id"] for r in sort_transfer_listings(rows, "highest_ovr")] == ["b", "c", "a"]
    assert [r["id"] for r in sort_transfer_listings(rows, "highest_potential")] == ["c", "b", "a"]
    assert [r["id"] for r in sort_transfer_listings(rows, "newest")] == ["b", "c", "a"]
    assert [r["id"] for r in sort_transfer_listings(rows, "ending_soon")] == ["b", "c", "a"]

    fair = {"a": 3000, "b": 2000, "c": 1000}  # ratios: 1.0, 0.5, 2.0 → b, a, c

    def fair_for(row: dict) -> int | None:
        return fair[row["id"]]

    assert [r["id"] for r in sort_transfer_listings(rows, "best_value", fair_value_for_row=fair_for)] == [
        "b",
        "a",
        "c",
    ]
    # unknown mode → newest
    assert [r["id"] for r in sort_transfer_listings(rows, "nope")] == ["b", "c", "a"]
    # input not mutated
    assert [r["id"] for r in rows] == ["a", "b", "c"]


def test_best_value_missing_fair_last():
    rows = _fixture_rows()

    def fair_for(row: dict) -> int | None:
        if row["id"] == "a":
            return None
        if row["id"] == "c":
            return 0
        return 2000  # b: 1000/2000 = 0.5

    ordered = sort_transfer_listings(rows, "best_value", fair_value_for_row=fair_for)
    assert ordered[0]["id"] == "b"
    assert {ordered[1]["id"], ordered[2]["id"]} == {"a", "c"}


def test_sort_modes_labels_cover_seven():
    assert len(SORT_MODES) == 7
    assert set(SORT_MODE_LABELS) == set(SORT_MODES)
