# apps/discord_bot/core/injury_rpc.py
"""Fatigue + post-match injury RPC wrappers (016 intensity tier)."""
from __future__ import annotations

import logging
import random
from typing import Any

from apps.discord_bot.core.card_payload import effective_card_age
from apps.discord_bot.core.match_cards import card_from_db_row
from match_engine import MatchPlayerCard
from match_engine.substitution_resolve import play_on_tier_upgrade
from player_engine import (
    TIER_NAMES,
    match_fatigue_drain,
    pick_bench_rest_ids,
    select_post_match_injury,
    stance_from_tactics_modifier,
)

logger = logging.getLogger(__name__)


def format_bench_rest_line(ok: bool, bench_count: int) -> str:
    """Short post-match copy for competitive bench rest / fitness failure."""
    if not ok:
        return (
            "⚠️ Fitness update failed — rewards still counted. "
            "Fatigue may update on retry."
        )
    if bench_count <= 0:
        return "Bench rest: no healthy reserves to rest."
    return f"Bench rest: +25 fitness for {bench_count} reserves (cap 100)."


def build_starter_drains(
    cards: list[dict[str, Any]],
    *,
    tactics_modifier: float = 1.0,
    intensity_tier: int = 1,
) -> dict[str, int]:
    stance = stance_from_tactics_modifier(tactics_modifier)
    drains: dict[str, int] = {}
    for card in cards:
        cid = str(card.get("id") or "")
        if not cid:
            continue
        phy = int(card.get("phy", 50))
        drains[cid] = match_fatigue_drain(
            phy, stance=stance, intensity_tier=intensity_tier
        )
    return drains


async def apply_match_fatigue_rpc(
    db: Any,
    owner_id: int,
    *,
    starter_drains: dict[str, int],
    bench_ids: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        "p_owner_id": owner_id,
        "p_starter_drains": starter_drains,
        "p_bench_ids": bench_ids or [],
    }
    res = await db.rpc("apply_match_fatigue", payload).execute()
    return res.data if isinstance(res.data, dict) else {"updated": 0}


def _finalize_recorded_injuries(
    recorded: list[dict[str, Any]],
    *,
    rng: random.Random | None = None,
) -> list[dict[str, Any]]:
    """Apply Play On tier upgrade; shape RPC payload."""
    r = rng or random.Random()
    out: list[dict[str, Any]] = []
    for item in recorded:
        cid = str(item.get("player_card_id") or "")
        if not cid:
            continue
        tier = int(item.get("tier") or 1)
        if item.get("play_on") or item.get("resolution") == "play_on":
            tier = play_on_tier_upgrade(tier, r)
        out.append({"player_card_id": cid, "tier": tier})
    return out


async def apply_post_match_fitness(
    db: Any,
    owner_id: int,
    *,
    starter_cards: list[dict[str, Any]],
    bench_ids: list[str] | None = None,
    tactics_modifier: float = 1.0,
    intensity_tier: int = 1,
    apply_injuries: bool = True,
    recorded_injuries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    After economy+XP: drain fatigue, then injuries.
    If recorded_injuries is non-empty (Phase 3 mid-match), persist those and
    skip a second A+C roll. Otherwise keep Phase 2 post-match roll.
    """
    drains = build_starter_drains(
        starter_cards,
        tactics_modifier=tactics_modifier,
        intensity_tier=intensity_tier,
    )
    fatigue_result = await apply_match_fatigue_rpc(
        db, owner_id, starter_drains=drains, bench_ids=bench_ids
    )

    injury_result: dict[str, Any] = {"admitted": [], "overflow": []}
    if apply_injuries:
        payload_injuries: list[dict[str, Any]] = []
        if recorded_injuries:
            payload_injuries = _finalize_recorded_injuries(recorded_injuries)
        elif starter_cards:
            ids = [str(c["id"]) for c in starter_cards if c.get("id")]
            refreshed: list[dict[str, Any]] = []
            if ids:
                rows = await db.table("player_cards").select(
                    "id, fatigue, phy, age, date_of_birth, injury_tier"
                ).in_("id", ids).execute()
                by_id = {str(r["id"]): r for r in (rows.data or [])}
                for c in starter_cards:
                    cid = str(c.get("id") or "")
                    row = by_id.get(cid, c)
                    if row.get("injury_tier"):
                        continue
                    refreshed.append({
                        "id": cid,
                        "fatigue": int(row.get("fatigue", c.get("fatigue", 100))),
                        "phy": int(row.get("phy", c.get("phy", 50))),
                        "age": effective_card_age(row),
                    })
            hit = select_post_match_injury(
                refreshed, intensity_tier=intensity_tier
            )
            if hit:
                payload_injuries = [
                    {"player_card_id": hit.player_card_id, "tier": hit.tier}
                ]

        if payload_injuries:
            res = await db.rpc(
                "process_post_match_injuries",
                {
                    "p_owner_id": owner_id,
                    "p_injuries": payload_injuries,
                },
            ).execute()
            if isinstance(res.data, dict):
                injury_result = res.data

    return {"fatigue": fatigue_result, "injuries": injury_result, "tier_names": TIER_NAMES}


async def fetch_bench_ids(db: Any, owner_id: int, starter_ids: list[str]) -> list[str]:
    """Owned non-retired cards not in the starting XI (for bench rest)."""
    rows = await db.table("player_cards").select(
        "id, injury_tier, overall, is_retired"
    ).eq("owner_id", owner_id).eq("is_retired", False).execute()
    return pick_bench_rest_ids(rows.data or [], starter_ids)


async def fetch_bench_cards(
    db: Any,
    owner_id: int,
    starter_ids: list[str],
) -> list[MatchPlayerCard]:
    """Hydrate up to 7 healthy bench MatchPlayerCards for Phase 3 subs."""
    ids = await fetch_bench_ids(db, owner_id, starter_ids)
    if not ids:
        return []
    rows = await db.table("player_cards").select("*").in_("id", ids).execute()
    by_id = {str(r["id"]): r for r in (rows.data or [])}
    return [card_from_db_row(by_id[i]) for i in ids if i in by_id]


def recorded_for_side(
    recorded: list[dict[str, Any]] | None,
    side: str,
) -> list[dict[str, Any]]:
    if not recorded:
        return []
    return [r for r in recorded if r.get("side") == side]


async def notify_injury_overflow(
    bot: Any,
    owner_id: int,
    overflow: list[dict[str, Any]],
) -> None:
    """Best-effort DM; Hospital panel is the fallback (SC-005)."""
    if not overflow:
        return
    try:
        user = await bot.fetch_user(owner_id)
        lines = []
        for item in overflow:
            tier = int(item.get("tier") or 1)
            lines.append(
                f"• Card `{item.get('player_card_id')}` — "
                f"{TIER_NAMES.get(tier, 'Injury')} (no bed free)"
            )
        await user.send(
            "**Hospital beds full.** Open `/profile` → **Manage Hospital** "
            "to discharge a patient or leave untreated.\n" + "\n".join(lines)
        )
    except Exception:
        logger.info("Injury overflow DM failed for %s (use Hospital panel)", owner_id)
