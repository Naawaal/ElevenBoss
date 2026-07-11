# tests/test_profile_hospital_summary.py
"""Pure formatter checks for /profile hospital + finance summary."""
from __future__ import annotations

from apps.discord_bot.embeds.profile_embeds import (
    HOSPITAL_UNAVAILABLE,
    L0_EMPTY,
    MAX_PATIENT_LINES,
    format_finance_section,
    format_hospital_summary,
)


def test_finance_section_shows_zero_gems() -> None:
    text = format_finance_section(12_450, 0)
    assert "12,450" in text
    assert "`0`" in text


def test_l0_empty_state_no_bed_fraction() -> None:
    text = format_hospital_summary(0, [{"expected_recovery_date": "2099-01-01"}])
    assert text == L0_EMPTY
    assert "/" not in text  # no occupied/capacity invention


def test_level_with_no_patients() -> None:
    text = format_hospital_summary(2, [])
    assert "Level 2" in text
    assert "0/3" in text  # beds = level + 1
    assert "No injuries" in text


def test_patient_truncation_cue() -> None:
    patients = [
        {"player_cards": {"name": f"P{i}"}, "expected_recovery_date": None}
        for i in range(MAX_PATIENT_LINES + 2)
    ]
    text = format_hospital_summary(3, patients)
    assert "P0" in text
    assert f"and **{2}** more" in text
    assert "Manage Hospital" in text


def test_unavailable_fallback() -> None:
    assert format_hospital_summary(2, [], unavailable=True) == HOSPITAL_UNAVAILABLE
