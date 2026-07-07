# apps/discord_bot/core/drill_rpc.py
"""Normalize process_stat_drill RPC payloads (028 flat keys vs 037 nested)."""
from __future__ import annotations


def parse_stat_drill_result(result: dict) -> dict:
    progression = result.get("progression") or {}
    xp_gained = int(
        result.get("xp_gained")
        or result.get("xp_gain")
        or progression.get("xp_added")
        or 0
    )
    levels_gained = int(
        result.get("levels_gained") or progression.get("levels_gained") or 0
    )
    skill_points_granted = int(
        result.get("skill_points_granted") or progression.get("skill_points_granted") or 0
    )
    new_level = int(
        result.get("new_level") or progression.get("new_level") or 1
    )
    coins_spent = int(result.get("coins_spent") or result.get("cost") or 0)

    energy_spent = result.get("energy_spent")
    if energy_spent is None:
        econ = result.get("economy") or {}
        energy_delta = econ.get("energy_delta")
        if energy_delta is not None:
            energy_spent = abs(int(energy_delta))
    energy_spent = int(energy_spent or 0)

    return {
        "xp_gained": xp_gained,
        "levels_gained": levels_gained,
        "skill_points_granted": skill_points_granted,
        "new_level": new_level,
        "coins_spent": coins_spent,
        "energy_spent": energy_spent,
    }
