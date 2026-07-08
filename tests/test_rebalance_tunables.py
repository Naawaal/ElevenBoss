from __future__ import annotations

from economy.flows import EconomyConfig, drill_cost
from player_engine.progression import drill_xp_reward


def test_drill_cost_uses_cfg_energy_values() -> None:
    cfg = EconomyConfig(
        drill_basic_energy=11,
        drill_advanced_energy=22,
        drill_advanced_min_level=10,
    )
    _coins, e = drill_cost(ovr=60, player_level=5, cfg=cfg)
    assert e == 11

    _coins, e = drill_cost(ovr=60, player_level=12, cfg=cfg)
    assert e == 22


def test_drill_xp_diminishing_returns_monotonic() -> None:
    base = 50
    xp_l1 = drill_xp_reward(base, player_level=1, age=None, training_ground_level=1)
    xp_l10 = drill_xp_reward(base, player_level=10, age=None, training_ground_level=1)
    xp_l25 = drill_xp_reward(base, player_level=25, age=None, training_ground_level=1)
    assert xp_l1 >= xp_l10 >= xp_l25


def test_regen_downtime_math_sanity() -> None:
    regen_per_min = 0.25  # 1 per 4 minutes (proposal target)
    minutes_per_energy = 1 / regen_per_min
    assert minutes_per_energy == 4
    assert 15 * minutes_per_energy == 60

