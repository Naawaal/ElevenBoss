# apps/discord_bot/core/match_xp.py
"""Build per-card match XP payloads for process_match_result (US-23 AC-23e)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from player_engine import MATCH_XP_DAILY_CAP, match_xp_reward

from apps.discord_bot.core.card_payload import effective_card_age
from apps.discord_bot.core.match_runs import mark_match_xp_applied

MATCH_MINUTES = 90

# Columns needed for match_xp_reward / effective_card_age (league recovery hydration).
_XP_CARD_SELECT = "id, name, age, date_of_birth"


@dataclass(frozen=True)
class MatchXpApplyResult:
    """Outcome of one process_match_result apply for UI copy."""

    total_granted: int = 0
    cards_granted: int = 0
    skipped: bool = False  # already applied / no cards
    attempted: bool = False


def format_match_xp_line(result: MatchXpApplyResult | None) -> str | None:
    """Player-facing one-liner for post-match Rewards (bot/league)."""
    if result is None or result.skipped:
        return None
    if not result.attempted:
        return None
    if result.total_granted <= 0:
        return (
            f"📈 Match XP: **0** — daily cap reached "
            f"({MATCH_XP_DAILY_CAP}/player)"
        )
    return (
        f"📈 Match XP: **+{result.total_granted}** across XI "
        f"({result.cards_granted} player"
        f"{'' if result.cards_granted == 1 else 's'}; "
        f"cap {MATCH_XP_DAILY_CAP}/day)"
    )


async def hydrate_cards_for_match_xp(db: Any, card_ids: list) -> list[dict]:
    """Load player_cards rows for XP apply, preserving input order. Skips missing ids."""
    if not card_ids:
        return []
    res = await db.table("player_cards").select(_XP_CARD_SELECT).in_("id", card_ids).execute()
    by_id = {str(row["id"]): row for row in (res.data or [])}
    return [by_id[str(cid)] for cid in card_ids if str(cid) in by_id]


def _goals_and_assists(
    player_name: str,
    club_name: str,
    key_events: list[dict],
) -> tuple[int, int]:
    goals = assists = 0
    for ev in key_events:
        if ev.get("type") != "GOAL":
            continue
        if ev.get("actor") == player_name and ev.get("team") == club_name:
            goals += 1
        if ev.get("assister") == player_name and ev.get("team") == club_name:
            assists += 1
    return goals, assists


def build_process_match_result_rpc(
    cards: list[dict],
    *,
    result: str,
    match_type: str,
    motm_name: str,
    key_events: list[dict],
    club_name: str,
    team_rating: float,
    minutes_played: int = MATCH_MINUTES,
) -> dict:
    """Return kwargs for Supabase RPC process_match_result with per-card XP."""
    card_ids: list = []
    xp_amounts: list[int] = []
    ratings: list[float] = []

    for card in cards:
        name = card["name"]
        goals, assists = _goals_and_assists(name, club_name, key_events)
        xp = match_xp_reward(
            minutes_played=minutes_played,
            match_rating=float(team_rating),
            match_type=match_type,
            goals=goals,
            assists=assists,
            motm=(name == motm_name),
            result=result,
            age=effective_card_age(card),
        )
        card_ids.append(card["id"])
        xp_amounts.append(xp)
        ratings.append(float(team_rating))

    return {
        "p_result": result,
        "p_card_ids": card_ids,
        "p_xp_amount": xp_amounts[0] if xp_amounts else 0,
        "p_xp_amounts": xp_amounts,
        "p_card_ratings": ratings,
    }


async def _sum_recent_match_xp(db: Any, card_ids: list, since_iso: str) -> tuple[int, int]:
    """Sum match_simulation XP logged for these cards since since_iso."""
    if not card_ids:
        return 0, 0
    ids = [str(cid) for cid in card_ids]
    res = (
        await db.table("player_xp_log")
        .select("card_id, xp_amount")
        .in_("card_id", ids)
        .eq("source", "match_simulation")
        .gte("created_at", since_iso)
        .execute()
    )
    rows = res.data or []
    total = sum(int(r.get("xp_amount") or 0) for r in rows)
    granted_cards = len({str(r["card_id"]) for r in rows if int(r.get("xp_amount") or 0) > 0})
    return total, granted_cards


async def apply_match_xp_if_needed(
    db: Any,
    *,
    history_id: str,
    existing_row: dict | None,
    cards: list[dict],
    result_str: str,
    match_type: str,
    motm_name: str,
    key_events: list[dict],
    club_name: str,
    team_rating: float,
) -> MatchXpApplyResult:
    """Apply process_match_result once per match_history row (crash-safe)."""
    if not cards:
        await mark_match_xp_applied(db, history_id)
        return MatchXpApplyResult(skipped=True)
    if existing_row and existing_row.get("xp_applied_at"):
        return MatchXpApplyResult(skipped=True)

    xp_payload = build_process_match_result_rpc(
        cards,
        result=result_str,
        match_type=match_type,
        motm_name=motm_name,
        key_events=key_events,
        club_name=club_name,
        team_rating=team_rating,
    )
    xp_payload["p_match_history_id"] = history_id
    since_iso = datetime.now(timezone.utc).isoformat()
    try:
        await db.rpc("process_match_result", xp_payload).execute()
    except Exception as exc:
        # FR-004: surface a stable message key for api_error_message mapping
        raise RuntimeError("Match XP could not be applied") from exc
    await mark_match_xp_applied(db, history_id)

    total, n_cards = await _sum_recent_match_xp(db, xp_payload["p_card_ids"], since_iso)
    return MatchXpApplyResult(
        total_granted=total,
        cards_granted=n_cards,
        attempted=True,
    )
