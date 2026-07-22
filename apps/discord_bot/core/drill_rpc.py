# apps/discord_bot/core/drill_rpc.py
"""Normalize process_stat_drill RPC payloads (028 flat keys vs 037 nested + 078 boost)."""
from __future__ import annotations


_BOOST_BLOCK_REASONS = frozenset({
    "stat_at_maximum",
    "at_potential",
    "would_exceed_potential",
})


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

    stat_boosted = bool(result.get("stat_boosted", False))
    raw_stat = result.get("stat")
    stat = str(raw_stat).upper() if raw_stat else None
    stat_delta = int(result.get("stat_delta") or (1 if stat_boosted else 0))
    new_stat_raw = result.get("new_stat_value")
    new_stat_value = int(new_stat_raw) if new_stat_raw is not None else None
    new_ovr_raw = result.get("new_ovr")
    new_ovr = int(new_ovr_raw) if new_ovr_raw is not None else None
    boost_block_reason = result.get("boost_block_reason")
    if boost_block_reason is not None:
        boost_block_reason = str(boost_block_reason)
        if boost_block_reason not in _BOOST_BLOCK_REASONS:
            # Unknown reason still surfaces; keep string for UI mapping fallback
            pass

    return {
        "xp_gained": xp_gained,
        "levels_gained": levels_gained,
        "skill_points_granted": skill_points_granted,
        "new_level": new_level,
        "coins_spent": coins_spent,
        "energy_spent": energy_spent,
        "stat_boosted": stat_boosted,
        "stat": stat,
        "stat_delta": stat_delta,
        "new_stat_value": new_stat_value,
        "new_ovr": new_ovr,
        "boost_block_reason": boost_block_reason,
    }


def humanize_boost_block_reason(reason: str | None) -> str:
    """Player-facing line for soft-failed attribute boost."""
    if reason == "stat_at_maximum":
        return "That attribute is already maxed"
    if reason == "at_potential":
        return "Player is already at potential overall"
    if reason == "would_exceed_potential":
        return "Raising that attribute would exceed potential"
    if reason:
        return "Attribute boost blocked"
    return "Attribute did not increase"
