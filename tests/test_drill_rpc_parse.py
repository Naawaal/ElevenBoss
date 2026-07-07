# tests/test_drill_rpc_parse.py
from __future__ import annotations

from apps.discord_bot.core.drill_rpc import parse_stat_drill_result


def test_parse_migration_028_flat_keys() -> None:
    parsed = parse_stat_drill_result(
        {
            "xp_gained": 42,
            "levels_gained": 1,
            "skill_points_granted": 3,
            "new_level": 8,
            "coins_spent": 244,
            "energy_spent": 15,
        }
    )
    assert parsed["xp_gained"] == 42
    assert parsed["coins_spent"] == 244
    assert parsed["energy_spent"] == 15
    assert parsed["levels_gained"] == 1


def test_parse_migration_037_nested_keys() -> None:
    """Regression: 037 renamed xp_gained→xp_gain and nested progression."""
    parsed = parse_stat_drill_result(
        {
            "xp_gain": 57,
            "cost": 316,
            "economy": {"energy_delta": -15, "coin_delta": -316},
            "progression": {
                "levels_gained": 0,
                "skill_points_granted": 0,
                "new_level": 12,
                "xp_added": 57,
            },
        }
    )
    assert parsed["xp_gained"] == 57
    assert parsed["coins_spent"] == 316
    assert parsed["energy_spent"] == 15
    assert parsed["new_level"] == 12
