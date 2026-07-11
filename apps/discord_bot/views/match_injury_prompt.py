# apps/discord_bot/views/match_injury_prompt.py
"""Phase 3 — mid-match injury Select + Play On (30s). Non-persistent."""
from __future__ import annotations

import asyncio
from typing import Any

import discord

from match_engine.substitution_resolve import (
    SubResolution,
    auto_resolve_injury,
)


class InjurySubView(discord.ui.View):
    """Match-scoped view; do not register with bot.add_view."""

    def __init__(
        self,
        *,
        state: Any,
        owner_id: int,
        injury_ev: dict,
        injured_player: Any,
        squad: list,
        bench: list,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.state = state
        self.owner_id = owner_id
        self.injury_ev = injury_ev
        self.injured_player = injured_player
        self.squad = squad
        self.bench = bench
        self._resolved = False

        options = injury_ev.get("options") or []
        bench_rows = injury_ev.get("bench") or []
        if "sub" in options and bench_rows:
            select = discord.ui.Select(
                placeholder="Choose a substitute…",
                options=[
                    discord.SelectOption(
                        label=f"{r['name']} ({r['position']}) OVR {r['overall']}"[:100],
                        value=str(r["card_id"]),
                        description=f"Fatigue {r.get('fatigue', '?')}"[:100],
                    )
                    for r in bench_rows[:25]
                ],
                custom_id="injury_sub_select",
            )
            select.callback = self._on_select  # type: ignore[method-assign]
            self.add_item(select)

        if "play_on" in options or not bench_rows:
            btn = discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="Play On",
                custom_id="injury_play_on",
            )
            btn.callback = self._on_play_on  # type: ignore[method-assign]
            self.add_item(btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the injured side's manager can decide.", ephemeral=True
            )
            return False
        return True

    def _signal(self, resolution: SubResolution) -> None:
        if self._resolved:
            return
        self._resolved = True
        self.state.sub_resolution = {
            "kind": resolution.kind,
            "injured_card_id": resolution.injured_card_id,
            "replacement_card_id": resolution.replacement_card_id,
            "tier": resolution.tier,
            "side": resolution.side,
            "play_on": resolution.kind == "play_on",
        }
        event = getattr(self.state, "sub_wait_event", None)
        if event is not None:
            event.set()
        self.stop()

    async def _on_select(self, interaction: discord.Interaction) -> None:
        values = interaction.data.get("values") if interaction.data else None  # type: ignore[union-attr]
        replacement_id = values[0] if values else None
        await interaction.response.defer(ephemeral=True)
        self._signal(
            SubResolution(
                kind="sub",
                injured_card_id=self.injury_ev.get("injured_card_id"),
                replacement_card_id=replacement_id,
                tier=int(self.injury_ev.get("injury_tier") or 1),
                side=str(self.injury_ev.get("side") or "home"),
            )
        )
        await interaction.followup.send("Substitution confirmed.", ephemeral=True)

    async def _on_play_on(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        self._signal(
            SubResolution(
                kind="play_on",
                injured_card_id=self.injury_ev.get("injured_card_id"),
                tier=int(self.injury_ev.get("injury_tier") or 1),
                side=str(self.injury_ev.get("side") or "home"),
                play_on=True,
            )
        )
        await interaction.followup.send(
            "Playing on through the injury — performance will suffer.",
            ephemeral=True,
        )

    async def on_timeout(self) -> None:
        if self._resolved:
            return
        side = str(self.injury_ev.get("side") or "home")
        res = auto_resolve_injury(
            side=side,
            injured=self.injured_player,
            bench=self.bench,
            squad=self.squad,
            subs_used=(
                self.state.subs_used_home if side == "home" else self.state.subs_used_away
            ),
            tier=int(self.injury_ev.get("injury_tier") or 1),
        )
        self._signal(res)


async def resolve_interactive_injury(
    *,
    channel: discord.abc.Messageable,
    state: Any,
    injury_ev: dict,
    owner_id: int,
    squad: list,
    bench: list,
    injured_player: Any,
) -> None:
    """Post InjurySubView and wait ≤30s. Writes state.sub_resolution."""
    wait_event = asyncio.Event()
    state.sub_wait_event = wait_event
    state.sub_resolution = None

    view = InjurySubView(
        state=state,
        owner_id=owner_id,
        injury_ev=injury_ev,
        injured_player=injured_player,
        squad=squad,
        bench=bench,
        timeout=30.0,
    )
    tier = int(injury_ev.get("injury_tier") or 1)
    tier_name = {1: "Minor", 2: "Moderate", 3: "Major"}.get(tier, "Injury")
    embed = discord.Embed(
        title=f"🩹 Injury stoppage — {injury_ev.get('injured_name', 'Player')}",
        description=(
            f"**{tier_name}** injury at {injury_ev.get('minute')}'\n"
            f"Subs remaining: **{injury_ev.get('subs_remaining', 0)}**\n"
            "Choose a substitute or **Play On** (30s)."
        ),
        color=0xE67E22,
    )
    await channel.send(embed=embed, view=view)
    try:
        await asyncio.wait_for(wait_event.wait(), timeout=31.0)
    except asyncio.TimeoutError:
        if not state.sub_resolution:
            side = str(injury_ev.get("side") or "home")
            res = auto_resolve_injury(
                side=side,
                injured=injured_player,
                bench=bench,
                squad=squad,
                subs_used=(
                    state.subs_used_home if side == "home" else state.subs_used_away
                ),
                tier=tier,
            )
            state.sub_resolution = {
                "kind": res.kind,
                "injured_card_id": res.injured_card_id,
                "replacement_card_id": res.replacement_card_id,
                "tier": res.tier,
                "side": res.side,
                "play_on": res.kind == "play_on",
            }
    finally:
        for child in view.children:
            child.disabled = True  # type: ignore[attr-defined]
        view.stop()
