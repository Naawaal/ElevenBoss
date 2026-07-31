# packages/leagues/leagues/expired_settle.py
"""Post-window expired fixture settle decision (048 / US-42.5).

AI clubs are always treated as eligible by the caller (pass home_ok/away_ok=True).
"""
from __future__ import annotations

from enum import Enum


class ExpiredSettleMode(str, Enum):
    SIM = "sim"
    FORFEIT_HOME = "forfeit_home"  # home illegal → 0–3
    FORFEIT_AWAY = "forfeit_away"  # away illegal → 3–0
    DOUBLE_FORFEIT = "double_forfeit"


def decide_expired_settle(*, home_ok: bool, away_ok: bool) -> ExpiredSettleMode:
    """Map eligibility to sim vs 026 forfeit modes."""
    if home_ok and away_ok:
        return ExpiredSettleMode.SIM
    if not home_ok and not away_ok:
        return ExpiredSettleMode.DOUBLE_FORFEIT
    if not home_ok:
        return ExpiredSettleMode.FORFEIT_HOME
    return ExpiredSettleMode.FORFEIT_AWAY


def played_fixture_status_label(result_type: str | None) -> str:
    """Fixtures hub suffix after the scoreline."""
    if result_type == "double_forfeit":
        return "Double Forfeit"
    if result_type == "forfeit":
        return "Forfeit"
    return "Full Time"
