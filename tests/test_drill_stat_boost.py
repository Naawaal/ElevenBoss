"""Drill attribute boost — parser + preview gate (036)."""
from __future__ import annotations

from apps.discord_bot.core.drill_rpc import humanize_boost_block_reason, parse_stat_drill_result
from player_engine import (
    DRILL_CATALOG,
    can_allocate_skill_point,
    drill_spec,
    stats_from_card,
)


def test_parse_boosted_payload() -> None:
    parsed = parse_stat_drill_result(
        {
            "xp_gain": 28,
            "cost": 220,
            "stat_boosted": True,
            "stat": "sho",
            "stat_delta": 1,
            "new_stat_value": 71,
            "new_ovr": 68,
            "boost_block_reason": None,
            "progression": {"xp_added": 28, "levels_gained": 0, "new_level": 4},
            "economy": {"energy_delta": -10},
        }
    )
    assert parsed["xp_gained"] == 28
    assert parsed["stat_boosted"] is True
    assert parsed["stat"] == "SHO"
    assert parsed["stat_delta"] == 1
    assert parsed["new_stat_value"] == 71
    assert parsed["new_ovr"] == 68
    assert parsed["boost_block_reason"] is None
    assert parsed["energy_spent"] == 10


def test_parse_missing_boost_keys_defaults_safe() -> None:
    parsed = parse_stat_drill_result({"xp_gain": 12, "cost": 100})
    assert parsed["stat_boosted"] is False
    assert parsed["stat"] is None
    assert parsed["stat_delta"] == 0
    assert parsed["new_stat_value"] is None
    assert parsed["new_ovr"] is None
    assert parsed["boost_block_reason"] is None


def test_parse_blocked_reasons() -> None:
    for reason in ("stat_at_maximum", "at_potential", "would_exceed_potential"):
        parsed = parse_stat_drill_result(
            {
                "xp_gain": 20,
                "stat_boosted": False,
                "stat": "PAC",
                "stat_delta": 0,
                "new_stat_value": None,
                "new_ovr": 82,
                "boost_block_reason": reason,
            }
        )
        assert parsed["stat_boosted"] is False
        assert parsed["stat_delta"] == 0
        assert parsed["boost_block_reason"] == reason
        assert "attribute" in humanize_boost_block_reason(reason).lower() or "potential" in humanize_boost_block_reason(reason).lower() or "maxed" in humanize_boost_block_reason(reason).lower()


def test_preview_gate_matches_catalog_stat() -> None:
    assert set(DRILL_CATALOG) == {
        "pac_sprint",
        "sho_finishing",
        "pas_distribution",
        "dri_dribble",
        "def_tackling",
        "phy_strength",
    }
    card = {
        "position": "FWD",
        "pac": 70,
        "sho": 70,
        "pas": 70,
        "dri": 70,
        "def": 40,
        "phy": 70,
        "overall": 72,
        "potential": 85,
        "playstyles": [],
    }
    for drill_id, meta in DRILL_CATALOG.items():
        spec = drill_spec(drill_id)
        assert spec is not None
        assert spec.stat == meta["stat"]
        ok, _ = can_allocate_skill_point(
            position="FWD",
            stats=stats_from_card(card),
            playstyles=[],
            potential=85,
            stat_key=spec.stat,
            overall=72,
        )
        assert ok is True

    capped = dict(card, sho=99)
    ok, reason = can_allocate_skill_point(
        position="FWD",
        stats=stats_from_card(capped),
        playstyles=[],
        potential=85,
        stat_key="sho",
        overall=72,
    )
    assert ok is False
    assert "maximum" in reason.lower()

    at_pot = dict(card, overall=85)
    ok, reason = can_allocate_skill_point(
        position="FWD",
        stats=stats_from_card(at_pot),
        playstyles=[],
        potential=85,
        stat_key="sho",
        overall=85,
    )
    assert ok is False
    assert "potential" in reason.lower()
