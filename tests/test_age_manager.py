# tests/test_age_manager.py
from __future__ import annotations

from datetime import date, timedelta

from player_engine import (
    LifecyclePhase,
    age_from_dob,
    apply_xp_age_multiplier,
    can_renew_contract,
    dob_from_age,
    lifecycle_phase,
    match_xp_reward,
    xp_multiplier,
    yearly_stat_decline,
)


def test_age_from_dob_round_trip() -> None:
    ref = date(2026, 7, 8)
    dob = dob_from_age(20, reference=ref)
    assert age_from_dob(dob, reference=ref) == 20


def test_lifecycle_phase_boundaries() -> None:
    assert lifecycle_phase(18) == LifecyclePhase.YOUTH
    assert lifecycle_phase(24) == LifecyclePhase.EARLY_PRIME
    assert lifecycle_phase(29) == LifecyclePhase.LATE_PRIME
    assert lifecycle_phase(33) == LifecyclePhase.VETERAN
    assert lifecycle_phase(36) == LifecyclePhase.RETIRING


def test_xp_multiplier_youth_vs_veteran() -> None:
    assert xp_multiplier(19) > xp_multiplier(33)


def test_match_xp_age_modifier() -> None:
    base = match_xp_reward(minutes_played=90, match_rating=7.0, match_type="bot", result="win")
    youth = match_xp_reward(minutes_played=90, match_rating=7.0, match_type="bot", result="win", age=18)
    veteran = match_xp_reward(minutes_played=90, match_rating=7.0, match_type="bot", result="win", age=33)
    assert youth > base
    assert veteran < base


def test_yearly_decline_veteran() -> None:
    assert yearly_stat_decline(30) == {}
    assert yearly_stat_decline(31) == {"pac": -1, "phy": -1}
    assert yearly_stat_decline(32) == {"pac": -1, "phy": -1}
    assert yearly_stat_decline(33) == {
        "pac": -1,
        "phy": -1,
        "pas": -1,
        "def": -1,
        "dri": -1,
    }
    assert yearly_stat_decline(34)["dri"] == -1
    assert "sho" not in yearly_stat_decline(34)
    d35 = yearly_stat_decline(35)
    assert d35["pac"] == -2
    assert d35["phy"] == -2
    assert d35["dri"] == -1
    assert d35["sho"] == -1
    assert yearly_stat_decline(36)["sho"] == -1


def test_can_renew_contract() -> None:
    assert can_renew_contract(34) is True
    assert can_renew_contract(35) is False


def test_create_player_card_has_dob() -> None:
    from player_engine import create_player_card

    data = create_player_card(
        position="MID",
        rarity="Common",
        target_ovr=60,
        first_name="Test",
        last_name="Player",
        age=19,
        reference_date=date(2026, 1, 1),
    )
    assert data.age == 19
    assert data.date_of_birth
    assert apply_xp_age_multiplier(10, 19) == 15
    assert data.role
