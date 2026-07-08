# apps/discord_bot/core/card_payload.py
"""Serialize gacha/player cards for Supabase RPC payloads."""
from __future__ import annotations

from datetime import date

from player_engine import age_from_dob


def card_rpc_payload(player) -> dict:
    """Build JSON payload for register_new_player / claim_daily_pack."""
    dob = getattr(player, "date_of_birth", None)
    if isinstance(dob, date):
        dob_str = dob.isoformat()
    else:
        dob_str = dob
    return {
        "name": player.name,
        "position": player.position,
        "rarity": player.rarity,
        "base_rating": player.base_rating,
        "overall": player.overall,
        "pac": player.pac,
        "sho": player.sho,
        "pas": player.pas,
        "dri": player.dri,
        "def": player.def_stat,
        "phy": player.phy,
        "potential": player.potential,
        "base_potential": player.potential,
        "age": player.age,
        "date_of_birth": dob_str,
    }


def scouting_pool_payload(card: dict, *, list_price: int) -> dict:
    """Build JSON for insert_scouting_pool_player RPC."""
    payload = dict(card)
    payload["list_price"] = list_price
    if "def" not in payload and "def_stat" in payload:
        payload["def"] = payload["def_stat"]
    return payload


def effective_card_age(card: dict, *, reference: date | None = None) -> int:
    """Resolve live age from DOB or fall back to cached age column."""
    dob_raw = card.get("date_of_birth")
    if dob_raw:
        if isinstance(dob_raw, str):
            dob = date.fromisoformat(dob_raw[:10])
        elif isinstance(dob_raw, date):
            dob = dob_raw
        else:
            dob = None
        if dob is not None:
            return age_from_dob(dob, reference=reference)
    return int(card.get("age") or 25)
