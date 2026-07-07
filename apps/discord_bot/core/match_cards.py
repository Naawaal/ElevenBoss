# apps/discord_bot/core/match_cards.py
"""Build MatchPlayerCard instances for live simulation."""
from __future__ import annotations

from typing import Any

from match_engine import MatchPlayerCard
from player_engine import apply_match_form


def card_from_db_row(row: dict[str, Any], playstyles: list[str] | None = None) -> MatchPlayerCard:
    """Map a player_cards row to MatchPlayerCard with morale-adjusted OVR."""
    base_ovr = int(row.get("overall", 50))
    morale = int(row.get("morale", 80))
    match_ovr = apply_match_form(base_ovr, morale)
    return MatchPlayerCard(
        name=row["name"],
        position=row["position"],
        overall=match_ovr,
        pac=int(row.get("pac", 50)),
        sho=int(row.get("sho", 50)),
        pas=int(row.get("pas", 50)),
        dri=int(row.get("dri", 50)),
        def_stat=int(row.get("def", 50)),
        phy=int(row.get("phy", 50)),
        morale=morale,
        playstyles=list(playstyles or []),
    )


async def fetch_playstyles(db, card_id: str) -> list[str]:
    ps_res = await db.table("player_playstyles").select("playstyle_key").eq("card_id", card_id).execute()
    return [p["playstyle_key"] for p in ps_res.data] if ps_res.data else []
