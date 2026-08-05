# packages/pvp/pvp/reward_policy.py
"""Mode reward policy — only Ranked PvP may produce non-zero Global LP, with opponent mode multipliers."""
from __future__ import annotations

from leagues.match_points import clamp_global_lp, global_lp_delta

from pvp.models import MatchMode, MatchResult, OpponentMode, RewardPolicyResult

PVP_ENERGY_DEFAULT = 20
PRACTICE_ENERGY_DEFAULT = 10
PVP_COIN_MULT = {"win": 1.25, "draw": 1.10, "loss": 1.00}
PRACTICE_NEW_MULT = 0.75
PRACTICE_ESTABLISHED_MULT = 0.50
PROVISIONAL_MATCHES = 5
PROVISIONAL_LOSS_FACTOR = 0.5  # reduced LP loss while provisional

# Mode multipliers for Ranked PvP backfill (Feature 054)
GHOST_COIN_MULT = 0.85
GHOST_XP_MULT = 0.90
GHOST_POS_LP_MULT = 0.75
GHOST_NEG_LP_MULT = 0.50

AI_BACKFILL_COIN_MULT = 0.70
AI_BACKFILL_XP_MULT = 0.75
AI_BACKFILL_POS_LP_MULT = 0.50
AI_BACKFILL_NEG_LP_MULT = 0.25


def reward_policy(
    mode: MatchMode,
    result: MatchResult,
    *,
    opponent_mode: OpponentMode = "live",
    snapshot_age_seconds: int | None = None,
    is_new_manager: bool = False,
    practice_rewards_enabled: bool = True,
) -> RewardPolicyResult:
    """Return multipliers and competitive flags for a match mode."""
    if mode == "pvp":
        if opponent_mode == "ghost":
            c_mult = PVP_COIN_MULT[result] * GHOST_COIN_MULT
            x_mult = GHOST_XP_MULT
            riv = False
            pvp_rec = False
        elif opponent_mode == "ai_backfill":
            c_mult = PVP_COIN_MULT[result] * AI_BACKFILL_COIN_MULT
            x_mult = AI_BACKFILL_XP_MULT
            riv = False
            pvp_rec = False
        else:
            c_mult = PVP_COIN_MULT[result]
            x_mult = 1.0
            riv = True
            pvp_rec = True

        return RewardPolicyResult(
            match_mode="pvp",
            opponent_mode=opponent_mode,
            energy_cost=PVP_ENERGY_DEFAULT,
            coin_multiplier=c_mult,
            xp_multiplier=x_mult,
            global_lp_delta=0,  # computed separately via pvp_lp_delta
            rivalry_counted=riv,
            updates_pvp_record=pvp_rec,
            snapshot_age_seconds=snapshot_age_seconds,
        )
    if mode == "practice":
        mult = PRACTICE_NEW_MULT if is_new_manager else PRACTICE_ESTABLISHED_MULT
        if not practice_rewards_enabled:
            mult = 0.0
        return RewardPolicyResult(
            match_mode="practice",
            opponent_mode="ai_backfill",
            energy_cost=PRACTICE_ENERGY_DEFAULT,
            coin_multiplier=mult,
            xp_multiplier=mult,
            global_lp_delta=0,
            rivalry_counted=False,
            updates_pvp_record=False,
        )
    return RewardPolicyResult(
        match_mode=mode,
        opponent_mode=opponent_mode,
        energy_cost=0 if mode == "friendly" else PRACTICE_ENERGY_DEFAULT,
        coin_multiplier=0.0 if mode == "friendly" else 1.0,
        xp_multiplier=0.0 if mode == "friendly" else 1.0,
        global_lp_delta=0,
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
    opponent_mode: OpponentMode = "live",
    ranked_matches_completed: int = 0,
    provisional_matches: int = PROVISIONAL_MATCHES,
    provisional_loss_factor: float = PROVISIONAL_LOSS_FACTOR,
) -> tuple[int, int]:
    """
    Ranked PvP LP change with provisional loss protection and opponent mode multipliers.

    Returns (new_lp, actual_delta).
    """
    raw = global_lp_delta(result)
    if (
        result == "loss"
        and ranked_matches_completed < provisional_matches
        and raw < 0
    ):
        raw = int(raw * provisional_loss_factor)

    if opponent_mode == "ghost":
        mult = GHOST_POS_LP_MULT if raw >= 0 else GHOST_NEG_LP_MULT
        raw = int(raw * mult)
    elif opponent_mode == "ai_backfill":
        mult = AI_BACKFILL_POS_LP_MULT if raw >= 0 else AI_BACKFILL_NEG_LP_MULT
        raw = int(raw * mult)

    return clamp_global_lp(current_lp, raw)


def practice_lp_delta() -> int:
    """AI Practice always awards zero competitive LP."""
    return 0
