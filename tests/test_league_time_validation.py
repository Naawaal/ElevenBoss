# tests/test_league_time_validation.py
from __future__ import annotations

import pytest

from leagues.league_time import (
    LeagueTimeError,
    coalesce_league_time,
    is_raw_utc_offset,
    league_time_preview,
    parse_resolution_hour,
    validate_iana_timezone,
)


def test_accepts_iana_timezone() -> None:
    assert validate_iana_timezone("Asia/Kathmandu") == "Asia/Kathmandu"
    assert validate_iana_timezone("UTC") == "UTC"


@pytest.mark.parametrize("raw", ["UTC+5:45", "UTC+0545", "GMT-4", "UTC-04:00", "+5:45"])
def test_rejects_raw_offsets(raw: str) -> None:
    assert is_raw_utc_offset(raw)
    with pytest.raises(LeagueTimeError):
        validate_iana_timezone(raw)


def test_rejects_unknown_zone() -> None:
    with pytest.raises(LeagueTimeError):
        validate_iana_timezone("Not/AZone")


@pytest.mark.parametrize("raw,expected", [("20", 20), ("20:00", 20), (0, 0), ("0", 0)])
def test_parse_hour(raw: object, expected: int) -> None:
    assert parse_resolution_hour(raw) == expected  # type: ignore[arg-type]


@pytest.mark.parametrize("raw", ["-1", "24", "xx", ""])
def test_parse_hour_rejects(raw: str) -> None:
    with pytest.raises(LeagueTimeError):
        parse_resolution_hour(raw)


def test_preview_copy_shape() -> None:
    text = league_time_preview("Asia/Kathmandu", 20, used_defaults=False)
    assert "Asia/Kathmandu" in text
    assert "next season" in text.lower()
    assert "UTC" in text
    assert "resolve daily" in text.lower()


def test_preview_mentions_defaults() -> None:
    text = league_time_preview("UTC", 0, used_defaults=True)
    assert "defaults" in text.lower()
