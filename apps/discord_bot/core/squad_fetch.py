# apps/discord_bot/core/squad_fetch.py
"""Fetch squad formation + slot-ordered XI for match simulation and pitch renders."""
from __future__ import annotations

from typing import Any

from apps.discord_bot.core.match_cards import card_from_db_row, fetch_playstyles
from apps.discord_bot.embeds.squad_embeds import get_slot_position
from match_engine import MatchPlayerCard


async def fetch_squad_xi(
    db,
    discord_id: int,
) -> tuple[str, dict[int, dict[str, Any]], list[dict[str, Any]]]:
    """Return (formation, slot->card, cards ordered by position_slot 1..11)."""
    squad_res = (
        await db.table("squads")
        .select("formation")
        .eq("discord_id", discord_id)
        .maybe_single()
        .execute()
    )
    formation = (
        squad_res.data.get("formation", "4-4-2")
        if squad_res and squad_res.data
        else "4-4-2"
    )

    assignments_res = (
        await db.table("squad_assignments")
        .select("position_slot, player_cards(*)")
        .eq("discord_id", discord_id)
        .order("position_slot")
        .execute()
    )
    by_slot: dict[int, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    for row in assignments_res.data or []:
        card = row.get("player_cards")
        if not card:
            continue
        slot = int(row["position_slot"])
        by_slot[slot] = card
        ordered.append(card)
    return formation, by_slot, ordered


def players_list_for_pitch(formation: str, assignments: dict[int, dict]) -> list[dict]:
    """Build 11 pitch slots in formation order (slot 1 = GK)."""
    players_list: list[dict] = []
    for slot in range(1, 12):
        card = assignments.get(slot)
        if card:
            players_list.append(
                {
                    "name": card["name"],
                    "overall": card["overall"],
                    "position": card["position"],
                    "rarity": card.get("rarity", "Common"),
                }
            )
        else:
            players_list.append(
                {
                    "name": "Empty Slot",
                    "overall": 0,
                    "position": get_slot_position(formation, slot),
                    "rarity": "Common",
                }
            )
    return players_list


async def ordered_cards_to_match_squad(
    db,
    ordered_cards: list[dict[str, Any]],
) -> list[MatchPlayerCard]:
    squad: list[MatchPlayerCard] = []
    for card in ordered_cards:
        playstyles = await fetch_playstyles(db, card["id"])
        squad.append(card_from_db_row(card, playstyles))
    return squad
