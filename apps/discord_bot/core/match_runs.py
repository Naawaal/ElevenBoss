# apps/discord_bot/core/match_runs.py
"""Durable match run records for restart recovery."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from match_engine import MatchPlayerCard


def generate_sim_seed() -> int:
    return secrets.randbits(63)


def _card_to_dict(card: MatchPlayerCard) -> dict[str, Any]:
    return {
        "name": card.name,
        "position": card.position,
        "overall": card.overall,
        "pac": card.pac,
        "sho": card.sho,
        "pas": card.pas,
        "dri": card.dri,
        "def_stat": card.def_stat,
        "phy": card.phy,
        "morale": card.morale,
        "playstyles": list(card.playstyles or []),
    }


def card_from_dict(data: dict[str, Any]) -> MatchPlayerCard:
    return MatchPlayerCard(
        name=data["name"],
        position=data["position"],
        overall=int(data["overall"]),
        pac=int(data.get("pac", 50)),
        sho=int(data.get("sho", 50)),
        pas=int(data.get("pas", 50)),
        dri=int(data.get("dri", 50)),
        def_stat=int(data.get("def_stat", 50)),
        phy=int(data.get("phy", 50)),
        morale=int(data.get("morale", 80)),
        playstyles=list(data.get("playstyles") or []),
    )


def build_league_snapshot(
    *,
    fixture: dict,
    home_name: str,
    away_name: str,
    home_rating: float,
    away_rating: float,
    home_squad: list[MatchPlayerCard],
    away_squad: list[MatchPlayerCard],
    home_cards: list[dict],
    away_cards: list[dict],
    home_formation: str = "4-4-2",
    away_formation: str = "4-4-2",
) -> dict[str, Any]:
    return {
        "fixture_id": fixture["id"],
        "season_id": fixture["season_id"],
        "matchday": fixture.get("matchday"),
        "home_team_id": fixture["home_team_id"],
        "away_team_id": fixture["away_team_id"],
        "home_name": home_name,
        "away_name": away_name,
        "home_rating": home_rating,
        "away_rating": away_rating,
        "home_is_ai": fixture["home"]["is_ai"],
        "away_is_ai": fixture["away"]["is_ai"],
        "home_formation": home_formation,
        "away_formation": away_formation,
        "home_squad": [_card_to_dict(c) for c in home_squad],
        "away_squad": [_card_to_dict(c) for c in away_squad],
        "home_card_ids": [c["id"] for c in home_cards],
        "away_card_ids": [c["id"] for c in away_cards],
    }


def squads_from_snapshot(snapshot: dict[str, Any]) -> tuple[list[MatchPlayerCard], list[MatchPlayerCard]]:
    home = [card_from_dict(c) for c in snapshot.get("home_squad", [])]
    away = [card_from_dict(c) for c in snapshot.get("away_squad", [])]
    return home, away


async def get_active_fixture_run(db, fixture_id: str) -> dict | None:
    res = await db.table("match_runs").select("*").eq("fixture_id", fixture_id).in_(
        "status", ["streaming", "completing"]
    ).maybe_single().execute()
    return res.data if res else None


async def create_league_run(
    db,
    *,
    fixture_id: str,
    active_discord_id: int | None,
    sim_seed: int,
    squad_snapshot: dict,
    guild_id: int | None,
    thread_id: int | None,
    home_discord_id: int,
    away_discord_id: int,
) -> dict:
    payload = {
        "run_type": "league",
        "status": "streaming",
        "fixture_id": fixture_id,
        "active_discord_id": active_discord_id,
        "home_discord_id": home_discord_id,
        "away_discord_id": away_discord_id,
        "sim_seed": sim_seed,
        "squad_snapshot": squad_snapshot,
        "guild_id": guild_id,
        "thread_id": thread_id,
    }
    res = await db.table("match_runs").insert(payload).execute()
    return (res.data or [payload])[0]


async def create_ephemeral_run(
    db,
    *,
    run_type: str,
    active_discord_id: int | None,
    home_discord_id: int | None,
    away_discord_id: int | None,
    sim_seed: int,
    guild_id: int | None,
    thread_id: int | None,
    squad_snapshot: dict | None = None,
) -> dict:
    payload = {
        "run_type": run_type,
        "status": "streaming",
        "active_discord_id": active_discord_id,
        "home_discord_id": home_discord_id,
        "away_discord_id": away_discord_id,
        "sim_seed": sim_seed,
        "squad_snapshot": squad_snapshot or {},
        "guild_id": guild_id,
        "thread_id": thread_id,
    }
    res = await db.table("match_runs").insert(payload).execute()
    return (res.data or [payload])[0]


async def mark_completing(db, run_id: str) -> None:
    await db.table("match_runs").update({
        "status": "completing",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", run_id).execute()


async def complete_run(db, run_id: str, *, home_score: int, away_score: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await db.table("match_runs").update({
        "status": "completed",
        "completion_key": run_id,
        "home_score": home_score,
        "away_score": away_score,
        "last_minute": 90,
        "completed_at": now,
        "updated_at": now,
    }).eq("id", run_id).execute()


async def abandon_match_run(db, run_id: str, *, reason: str | None = None) -> Any:
    """Terminal abandon via RPC — clears locks for home/away/active."""
    params: dict[str, Any] = {"p_run_id": run_id}
    if reason is not None:
        params["p_reason"] = reason
    res = await db.rpc("abandon_match_run", params).execute()
    return res.data


async def abandon_run(db, run_id: str, *, reason: str | None = None) -> None:
    """Abandon interrupted run (RPC; releases match locks)."""
    await abandon_match_run(db, run_id, reason=reason)


async def reconcile_orphaned_match_locks(db) -> int:
    res = await db.rpc("reconcile_orphaned_match_locks", {}).execute()
    data = res.data
    if data is None:
        return 0
    if isinstance(data, int):
        return data
    try:
        return int(data)
    except (TypeError, ValueError):
        return 0


async def league_history_exists(db, player_id: int, fixture_id: str) -> bool:
    res = await db.table("match_history").select("id").eq(
        "player_id", player_id
    ).eq("fixture_id", fixture_id).maybe_single().execute()
    return bool(res and res.data)


async def fetch_match_reward_row(
    db,
    player_id: int,
    *,
    fixture_id: str | None = None,
    run_id: str | None = None,
) -> dict | None:
    """Return match_history reward row for idempotent economy/XP application."""
    if fixture_id:
        res = await db.table("match_history").select(
            "id, coins_earned, points_earned, xp_applied_at, fatigue_applied_at"
        ).eq("player_id", player_id).eq("fixture_id", fixture_id).maybe_single().execute()
    elif run_id:
        res = await db.table("match_history").select(
            "id, coins_earned, points_earned, xp_applied_at, fatigue_applied_at"
        ).eq("player_id", player_id).eq("run_id", run_id).maybe_single().execute()
    else:
        return None
    return res.data if res and res.data else None


async def mark_match_xp_applied(db, history_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await db.table("match_history").update({"xp_applied_at": now}).eq("id", history_id).execute()


async def mark_match_fatigue_applied(db, history_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await db.table("match_history").update({"fatigue_applied_at": now}).eq("id", history_id).execute()
