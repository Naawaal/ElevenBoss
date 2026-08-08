# apps/discord_bot/core/competitive_match.py
"""Competitive Bot Match helpers — discipline payload, result, stadium tiers (057)."""
from __future__ import annotations

from typing import Any

from match_engine.competitive_models import competitive_snapshot


TIER_A = frozenset({
    "KICKOFF", "HALF_TIME", "FULL_TIME", "GOAL", "INJURY",
    "RED_CARD", "EXTRA_TIME_START", "EXTRA_TIME_BREAK",
    "PENALTY_SHOOTOUT_START", "PENALTY_KICK",
})
TIER_B = frozenset({"YELLOW_CARD", "SAVE", "MISS", "FOUL", "CHANCE"})


def event_presentation_tier(event_type: str) -> str:
    et = str(event_type or "")
    if et in TIER_A:
        return "A"
    if et in TIER_B:
        return "B"
    return "C"


def competitive_result_str(state: Any) -> str:
    """Win/draw/loss including penalty shootout winner; football score may stay level."""
    decided = getattr(state, "decided_by", None)
    if decided == "penalties":
        hp = int(getattr(state, "home_penalties", 0) or 0)
        ap = int(getattr(state, "away_penalties", 0) or 0)
        if hp > ap:
            return "win"
        if ap > hp:
            return "loss"
        # should not happen if shootout completed
    hs = int(getattr(state, "home_score", 0) or 0)
    aws = int(getattr(state, "away_score", 0) or 0)
    if hs > aws:
        return "win"
    if hs < aws:
        return "loss"
    return "draw"


def snapshot_from_state(state: Any) -> dict[str, Any]:
    return competitive_snapshot(
        phase=getattr(state, "match_phase", "REGULATION") or "REGULATION",
        phase_minute=int(getattr(state, "minute", 0) or 0),
        home_score=int(getattr(state, "home_score", 0) or 0),
        away_score=int(getattr(state, "away_score", 0) or 0),
        decided_by=getattr(state, "decided_by", None),
        penalty_state=getattr(state, "penalty_state", None),
        home_penalties=int(getattr(state, "home_penalties", 0) or 0),
        away_penalties=int(getattr(state, "away_penalties", 0) or 0),
        et1_seed=None,
        et2_seed=None,
        shootout_seed=None,
    )


def dismissals_for_rpc(state: Any, home_squad: list[Any]) -> list[dict[str, str]]:
    """Map home-side dismissals to player_card_id for apply_bot_match_discipline."""
    by_name: dict[str, str] = {}
    for p in home_squad:
        name = getattr(p, "name", None) or (p.get("name") if isinstance(p, dict) else None)
        cid = getattr(p, "card_id", None) or (
            p.get("card_id") or p.get("id") if isinstance(p, dict) else None
        )
        if name and cid:
            by_name[str(name)] = str(cid)

    out: list[dict[str, str]] = []
    for d in getattr(state, "dismissals", None) or []:
        pname = str(d.get("player_name") or "")
        cid = by_name.get(pname)
        if not cid:
            continue
        reason = str(d.get("reason") or "")
        if reason not in ("second_yellow", "straight_red"):
            continue
        out.append({"player_card_id": cid, "reason": reason})
    return out


def format_scoreline(state: Any) -> str:
    hs = int(getattr(state, "home_score", 0) or 0)
    aws = int(getattr(state, "away_score", 0) or 0)
    decided = getattr(state, "decided_by", None)
    if decided == "penalties":
        hp = int(getattr(state, "home_penalties", 0) or 0)
        ap = int(getattr(state, "away_penalties", 0) or 0)
        return f"{hs}–{aws} ({hp}–{ap} pens)"
    if decided == "extra_time" or getattr(state, "played_extra_time", False):
        if hs != aws:
            return f"{hs}–{aws} (AET)"
    return f"{hs}–{aws}"


def format_shootout_emoji_line(penalty_state: dict | None) -> str:
    """Single-message shootout progress: 🟢 miss/save ❌."""
    if not penalty_state:
        return ""
    events = penalty_state.get("events") or []
    parts: list[str] = []
    for ev in events:
        side = "H" if ev.get("club_side") == "home" else "A"
        mark = "🟢" if ev.get("outcome") == "goal" else "❌"
        parts.append(f"{side}{mark}")
    return " ".join(parts)
