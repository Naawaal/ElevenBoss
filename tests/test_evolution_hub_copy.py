"""Hub cost-copy mirrors for evolution start (package constants + formula line)."""
from __future__ import annotations

from player_engine import (
    EVOLUTION_START_COOLDOWN_HOURS,
    EVOLUTION_START_ENERGY,
    EVOLUTION_START_FLAT,
    EVOLUTION_START_OVR_MULT,
    evolution_hub_start_cost_line,
)


def test_evolution_start_constants_match_live_mirrors() -> None:
    assert EVOLUTION_START_ENERGY == 25
    assert EVOLUTION_START_FLAT == 500
    assert EVOLUTION_START_OVR_MULT == 5
    assert EVOLUTION_START_COOLDOWN_HOURS == 6


def test_hub_start_cost_line_uses_flat_plus_ovr_not_legacy_10x() -> None:
    line = evolution_hub_start_cost_line()
    assert "10×OVR" not in line
    assert "500+5×OVR" in line
    assert "25 energy" in line


def test_hub_start_cost_line_prefers_status_overrides() -> None:
    line = evolution_hub_start_cost_line(energy=30, flat=400, ovr_mult=7)
    assert "`30 energy` + `400+7×OVR` coins per track" == line
