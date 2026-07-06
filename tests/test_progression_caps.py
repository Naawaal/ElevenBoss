# tests/test_progression_caps.py
"""Regression: stat training must respect POT ceiling and 99 stat cap."""
from __future__ import annotations

import json
import time

import random

from player_engine import (
    calculate_true_ovr,
    can_gain_stat_progression,
    detect_stat_inflation,
    rebalance_stats_to_ovr,
    simulate_legacy_stat_drill,
)

_DEBUG_LOG = "debug-4aa967.log"
_SESSION = "4aa967"


def _log(hypothesis_id: str, location: str, message: str, data: dict, run_id: str = "pre-fix") -> None:
    # #region agent log
    try:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": _SESSION,
                        "runId": run_id,
                        "hypothesisId": hypothesis_id,
                        "timestamp": int(time.time() * 1000),
                        "location": location,
                        "message": message,
                        "data": data,
                    }
                )
                + "\n"
            )
    except OSError:
        pass
    # #endregion


def test_hypothesis_a_drill_allowed_at_pot_ceiling() -> None:
    """H-A: legacy drill logic allows stat +1 when overall == potential."""
    overall, potential, sho = 60, 60, 60
    allowed, reason = can_gain_stat_progression(
        overall=overall, potential=potential, stat_value=sho
    )
    _log("A", "test_progression_caps.py", "gate at POT ceiling", {
        "overall": overall, "potential": potential, "sho": sho,
        "allowed": allowed, "reason": reason,
    })
    assert not allowed
    assert "potential" in reason.lower()

    sim = simulate_legacy_stat_drill(overall=overall, potential=potential, stat_value=sho)
    _log("A", "test_progression_caps.py", "legacy sim at POT", sim)
    assert sim["levels_gained"] == 1
    assert sim["new_stat"] == 61
    assert sim["new_ovr"] == 60


def test_hypothesis_b_stat_99_still_charges_legacy() -> None:
    """H-B: legacy drill charges energy/coins when stat already 99."""
    sim = simulate_legacy_stat_drill(overall=55, potential=70, stat_value=99)
    _log("B", "test_progression_caps.py", "legacy sim at stat 99", sim)
    assert sim["levels_gained"] == 0
    assert sim["charged"] is True

    allowed, reason = can_gain_stat_progression(overall=55, potential=70, stat_value=99)
    assert not allowed
    assert "maximum" in reason.lower()


def test_hypothesis_c_ovr_stays_capped_while_stat_inflates() -> None:
    """H-C: pumping one stat creates hidden power above OVR at POT."""
    stats = {"pac": 60, "sho": 60, "pas": 60, "dri": 60, "def": 60, "phy": 60}
    potential = 60
    ovr_before = calculate_true_ovr("FWD", stats, [], potential)
    stats["sho"] = 99
    ovr_after = calculate_true_ovr("FWD", stats, [], potential)
    _log("C", "test_progression_caps.py", "god player inflation", {
        "ovr_before": ovr_before,
        "ovr_after": ovr_after,
        "sho_after": 99,
        "potential": potential,
        "stat_delta": 99 - 60,
    })
    assert ovr_before == 60
    assert ovr_after == 60
    assert stats["sho"] == 99


def test_hypothesis_d_gate_blocks_post_fix() -> None:
    """H-D: fixed gates block both failure modes."""
    cases = [
        (60, 60, 70, False),
        (55, 70, 99, False),
        (58, 60, 80, True),
    ]
    for overall, potential, stat, expect in cases:
        ok, _ = can_gain_stat_progression(overall=overall, potential=potential, stat_value=stat)
        _log("D", "test_progression_caps.py", "gate matrix", {
            "overall": overall, "potential": potential, "stat": stat, "allowed": ok,
        }, run_id="post-fix")
        assert ok is expect


def test_detect_god_player_inflation() -> None:
    stats = {"pac": 60, "sho": 99, "pas": 60, "dri": 60, "def": 60, "phy": 60}
    inflated, info = detect_stat_inflation("FWD", stats, [], 60, 60)
    _log("F", "test_progression_caps.py", "detect god player", info, run_id="backfill")
    assert inflated
    assert info["hidden_power"] > 1


def test_rebalance_clears_hidden_power() -> None:
    stats = {"pac": 60, "sho": 99, "pas": 60, "dri": 60, "def": 60, "phy": 60}
    rng = random.Random(42)
    new_stats = rebalance_stats_to_ovr("FWD", 60, [], 60, rng=rng)
    inflated, info = detect_stat_inflation("FWD", new_stats, [], 60, 60)
    _log("F", "test_progression_caps.py", "after rebalance", {
        "new_stats": new_stats,
        **info,
    }, run_id="backfill")
    assert not inflated
    assert info["hidden_power"] <= 1
    assert max(new_stats.values()) < 99
    assert calculate_true_ovr("FWD", new_stats, [], 60) == 60
