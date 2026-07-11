# apps/discord_bot/core/card_payload.py
"""Serialize gacha/player cards for Supabase RPC payloads."""
from __future__ import annotations

from datetime import date

from player_engine import age_from_dob


def card_rpc_payload(player) -> dict:
    """Build JSON payload for register_new_player / claim_daily_pack / youth intake."""
    dob = getattr(player, "date_of_birth", None)
    if isinstance(dob, date):
        dob_str = dob.isoformat()
    else:
        dob_str = dob
    base_pot = getattr(player, "base_potential", None)
    if base_pot is None:
        base_pot = player.potential
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
        "base_potential": base_pot,
        "age": player.age,
        "date_of_birth": dob_str,
        "role": getattr(player, "role", None) or "Balanced",
    }


def scouting_pool_payload(card, *, list_price: int) -> dict:
    """Build JSON for insert_scouting_pool_player RPC (apps edge — dict only here)."""
    if hasattr(card, "model_dump"):
        payload = card.model_dump(by_alias=True)
    elif isinstance(card, dict):
        payload = dict(card)
    else:
        payload = card_rpc_payload(card)
        src = getattr(card, "source_card_id", None)
        if src:
            payload["source_card_id"] = src
    payload["list_price"] = list_price
    if "def" not in payload and "def_stat" in payload:
        payload["def"] = payload.pop("def_stat")
    if "role" not in payload or not payload["role"]:
        payload["role"] = "Balanced"
    # Drop None optional keys that confuse jsonb casts
    if payload.get("source_card_id") is None:
        payload.pop("source_card_id", None)
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
