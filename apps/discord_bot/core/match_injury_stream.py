# apps/discord_bot/core/match_injury_stream.py
"""Shared live-stream injury pause helper (Phase 3)."""
from __future__ import annotations

from typing import Any

import discord

from apps.discord_bot.views.match_injury_prompt import resolve_interactive_injury
from match_engine.substitution_resolve import auto_resolve_injury


def _find_by_id(squad: list, card_id: str | None) -> Any | None:
    if not card_id:
        return None
    for p in squad:
        cid = getattr(p, "card_id", None) or (p.get("id") if isinstance(p, dict) else None)
        if cid is not None and str(cid) == str(card_id):
            return p
    return None


async def handle_injury_event(
    *,
    ev: dict,
    state: Any,
    channel: discord.abc.Messageable | None,
    home_squad: list,
    away_squad: list,
    owner_by_side: dict[str, int],
    silent: bool = False,
) -> str | None:
    """
    If interactive human injury: pause for Select UI.
    Else: ensure auto-resolution is written for the generator's consume step.
    Returns optional ticker suffix line.
    """
    if ev.get("type") != "INJURY":
        return None

    side = str(ev.get("side") or "home")
    squad = home_squad if side == "home" else away_squad
    bench = list(state.bench_home if side == "home" else state.bench_away)
    injured = _find_by_id(squad, ev.get("injured_card_id"))
    suffix = None
    tags = []
    if "substitution" in (state.context_tags or []):
        tags.append("sub")
    if ev.get("gk_emergency"):
        tags.append("emergency GK")

    interactive = bool(ev.get("interactive")) and not silent and channel is not None
    owner_id = owner_by_side.get(side)

    if interactive and owner_id and injured is not None:
        await resolve_interactive_injury(
            channel=channel,
            state=state,
            injury_ev=ev,
            owner_id=owner_id,
            squad=squad,
            bench=bench,
            injured_player=injured,
        )
        kind = (state.sub_resolution or {}).get("kind")
        if kind == "sub":
            suffix = "🔄 Substitution made."
        elif kind == "play_on":
            suffix = "💪 Playing on through injury."
        elif kind == "emergency_gk":
            suffix = "🧤 Emergency goalkeeper!"
        elif kind == "ten_men":
            suffix = "📉 Down to ten men."
    elif not state.sub_resolution and injured is not None:
        # Non-interactive / AI — pre-seed so consume uses this (optional; consume also autos)
        res = auto_resolve_injury(
            side=side,
            injured=injured,
            bench=bench,
            squad=squad,
            subs_used=(state.subs_used_home if side == "home" else state.subs_used_away),
            tier=int(ev.get("injury_tier") or 1),
        )
        state.sub_resolution = {
            "kind": res.kind,
            "injured_card_id": res.injured_card_id,
            "replacement_card_id": res.replacement_card_id,
            "tier": res.tier,
            "side": res.side,
            "play_on": res.kind == "play_on",
        }
        if res.kind == "ten_men":
            suffix = "📉 Down to ten men."
        elif res.kind == "sub":
            suffix = "🔄 Auto-substitution."
        elif res.kind == "emergency_gk":
            suffix = "🧤 Emergency goalkeeper!"

    return suffix
