# packages/pvp/pvp/reward_policy.py
"""Mode reward policy — only Ranked PvP may produce non-zero Global LP."""
from __future__ import annotations

from leagues.match_points import clamp_global_lp, global_lp_delta

from pvp.models import MatchMode, MatchResult, RewardPolicyResult

PVP_ENERGY_DEFAULT = 20
PRACTICE_ENERGY_DEFAULT = 10
PVP_COIN_MULT = {"win": 1.25, "draw": 1.10, "loss": 1.00}
PRACTICE_NEW_MULT = 0.75
PRACTICE_ESTABLISHED_MULT = 0.50
PROVISIONAL_MATCHES = 5
PROVISIONAL_LOSS_FACTOR = 0.5  # reduced LP loss while provisional


def reward_policy(
    mode: MatchMode,
    result: MatchResult,
    *,
    is_new_manager: bool = False,
    practice_rewards_enabled: bool = True,
) -> RewardPolicyResult:
    """Return multipliers and competitive flags for a match mode."""
    if mode == "pvp":
        return RewardPolicyResult(
            match_mode="pvp",
            energy_cost=PVP_ENERGY_DEFAULT,
            coin_multiplier=PVP_COIN_MULT[result],
            xp_multiplier=1.0,
            global_lp_delta=0,  # computed separately via pvp_lp_delta
            rivalry_counted=True,
            updates_pvp_record=True,
        )
    if mode == "practice":
        mult = PRACTICE_NEW_MULT if is_new_manager else PRACTICE_ESTABLISHED_MULT
        if not practice_rewards_enabled:
            mult = 0.0
        return RewardPolicyResult(
            match_mode="practice",
            energy_cost=PRACTICE_ENERGY_DEFAULT,
            coin_multiplier=mult,
            xp_multiplier=mult,
            global_lp_delta=0,
            rivalry_counted=False,
            updates_pvp_record=False,
        )
    # friendly / league / bot legacy — competitive LP never from friendly
    return RewardPolicyResult(
        match_mode=mode,
        energy_cost=0 if mode == "friendly" else PRACTICE_ENERGY_DEFAULT,
        coin_multiplier=0.0 if mode == "friendly" else 1.0,
        xp_multiplier=0.0 if mode == "friendly" else 1.0,
        global_lp_delta=0 if mode in ("friendly", "practice") else 0,
        rivalry_counted=False,
        updates_pvp_record=False,
    )


def assert_lp_allowed(mode: MatchMode, lp_delta: int) -> None:
    """Raise if a non-pvp mode attempts a non-zero LP delta."""
    if mode != "pvp" and lp_delta != 0:
        raise ValueError(f"match_mode={mode!r} cannot apply global_lp_delta={lp_delta}")


def pvp_lp_delta(
    result: MatchResult,
    *,
    current_lp: int,
    ranked_matches_completed: int = 0,
    provisional_matches: int = PROVISIONAL_MATCHES,
    provisional_loss_factor: float = PROVISIONAL_LOSS_FACTOR,
) -> tuple[int, int]:
    """
    Ranked PvP LP change with provisional loss protection.

    Returns (new_lp, actual_delta). Non-pvp callers must not use this for Practice.
    """
    raw = global_lp_delta(result)
    if (
        result == "loss"
        and ranked_matches_completed < provisional_matches
        and raw < 0
    ):
        raw = int(raw * provisional_loss_factor)
    return clamp_global_lp(current_lp, raw)


def practice_lp_delta() -> int:
    """AI Practice always awards zero competitive LP."""
    return 0
