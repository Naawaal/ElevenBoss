# apps/discord_bot/views/rivalries_view.py
"""Manager Rivalries hub UI (Feature 053 US5/US6) — presentation only."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord

from apps.discord_bot.core.api_errors import api_error_message
from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from apps.discord_bot.embeds.pvp_embeds import (
    hottest_rivalries_embed,
    rivalries_list_embed,
    rivalry_detail_embed,
)

if TYPE_CHECKING:
    from apps.discord_bot.cogs.battle_cog import BattleCog

logger = logging.getLogger(__name__)


class RivalriesHubView(discord.ui.View):
    def __init__(self, cog: BattleCog, owner_id: int, guild_id: int, rivals: list[dict[str, Any]]) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.rivals = rivals
        options = [
            discord.SelectOption(
                label=f"vs {r.get('opponent_id')}"[:100],
                value=str(r.get("opponent_id")),
                description=f"{r.get('status')} · {r.get('my_wins', 0)}–{r.get('their_wins', 0)}"[:100],
            )
            for r in rivals[:25]
            if r.get("opponent_id") is not None
        ]
        if options:
            self.add_item(RivalSelect(options))
        self.add_item(HottestBoardButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True


class RivalSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(placeholder="Open a rivalry…", options=options, custom_id="rivalry_pick")

    async def callback(self, interaction: discord.Interaction) -> None:
        view: RivalriesHubView = self.view  # type: ignore[assignment]
        await interaction.response.defer(ephemeral=True)
        opp = int(self.values[0])
        db = await get_client()
        try:
            res = await db.rpc(
                "get_rivalry_detail",
                {"p_viewer_id": interaction.user.id, "p_opponent_id": opp},
            ).execute()
            detail = res.data if isinstance(res.data, dict) else {}
        except Exception as exc:
            await interaction.followup.send(embed=error_embed(api_error_message(exc)), ephemeral=True)
            return
        if not detail.get("found"):
            await interaction.followup.send(embed=error_embed("Rivalry not found."), ephemeral=True)
            return
        embed = rivalry_detail_embed(detail, opponent_id=opp, viewer_id=interaction.user.id)
        await interaction.followup.send(
            embed=embed,
            view=RivalryDetailView(view.cog, interaction.user.id, opp, detail),
            ephemeral=True,
        )


class HottestBoardButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(style=discord.ButtonStyle.secondary, label="🌡️ Server Board", custom_id="rivalries_hottest")

    async def callback(self, interaction: discord.Interaction) -> None:
        view: RivalriesHubView = self.view  # type: ignore[assignment]
        await interaction.response.defer(ephemeral=True)
        db = await get_client()
        try:
            res = await db.rpc(
                "get_server_hottest_rivalries",
                {"p_guild_id": view.guild_id or 0, "p_limit": 10},
            ).execute()
            payload = res.data if isinstance(res.data, dict) else {}
        except Exception as exc:
            await interaction.followup.send(embed=error_embed(api_error_message(exc)), ephemeral=True)
            return
        await interaction.followup.send(embed=hottest_rivalries_embed(payload), ephemeral=True)


class RivalryDetailView(discord.ui.View):
    def __init__(self, cog: BattleCog, owner_id: int, opponent_id: int, detail: dict[str, Any]) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_id = owner_id
        self.opponent_id = opponent_id
        self.detail = detail
        blocked = bool(detail.get("blocked"))
        self.add_item(FriendlyRematchButton())
        self.add_item(BlockRivalButton(blocked=blocked))
        self.add_item(TogglePrefButton("dms", "DMs"))
        self.add_item(TogglePrefButton("callouts", "Callouts"))
        self.add_item(TogglePrefButton("lb_visible", "LB Visible"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True


class FriendlyRematchButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(
            style=discord.ButtonStyle.success,
            label="🤝 Friendly Rematch",
            custom_id="rivalry_friendly_rematch",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: RivalryDetailView = self.view  # type: ignore[assignment]
        await interaction.response.send_message(
            f"Friendly Rematch is sandbox-only (no LP / rivalry). "
            f"Run `/battle friendly opponent:<@{view.opponent_id}>`.",
            ephemeral=True,
        )


class BlockRivalButton(discord.ui.Button):
    def __init__(self, *, blocked: bool) -> None:
        label = "Unblock" if blocked else "Block"
        style = discord.ButtonStyle.secondary if blocked else discord.ButtonStyle.danger
        super().__init__(style=style, label=label, custom_id="rivalry_block_toggle")
        self.blocked = blocked

    async def callback(self, interaction: discord.Interaction) -> None:
        view: RivalryDetailView = self.view  # type: ignore[assignment]
        await interaction.response.defer(ephemeral=True)
        db = await get_client()
        new_block = not self.blocked
        try:
            await db.rpc(
                "set_pvp_block",
                {
                    "p_blocker_id": interaction.user.id,
                    "p_blocked_id": view.opponent_id,
                    "p_blocked": new_block,
                },
            ).execute()
        except Exception as exc:
            await interaction.followup.send(embed=error_embed(api_error_message(exc)), ephemeral=True)
            return
        self.blocked = new_block
        self.label = "Unblock" if new_block else "Block"
        self.style = discord.ButtonStyle.secondary if new_block else discord.ButtonStyle.danger
        await interaction.followup.send(
            embed=success_embed("Manager blocked." if new_block else "Manager unblocked."),
            ephemeral=True,
        )


class TogglePrefButton(discord.ui.Button):
    def __init__(self, pref_key: str, label: str) -> None:
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=f"Toggle {label}",
            custom_id=f"rivalry_pref_{pref_key}",
            row=1,
        )
        self.pref_key = pref_key

    async def callback(self, interaction: discord.Interaction) -> None:
        view: RivalryDetailView = self.view  # type: ignore[assignment]
        await interaction.response.defer(ephemeral=True)
        prefs = dict(view.detail.get("prefs") or {})
        current = bool(prefs.get(self.pref_key, True))
        new_val = not current
        kwargs: dict[str, Any] = {"p_owner_id": interaction.user.id}
        if self.pref_key == "dms":
            kwargs["p_rivalry_dms"] = new_val
        elif self.pref_key == "callouts":
            kwargs["p_rivalry_callouts"] = new_val
        else:
            kwargs["p_rivalry_lb_visible"] = new_val
        db = await get_client()
        try:
            await db.rpc("set_pvp_prefs", kwargs).execute()
        except Exception as exc:
            await interaction.followup.send(embed=error_embed(api_error_message(exc)), ephemeral=True)
            return
        prefs[self.pref_key] = new_val
        view.detail["prefs"] = prefs
        await interaction.followup.send(
            embed=success_embed(f"{self.pref_key} → {'on' if new_val else 'off'}"),
            ephemeral=True,
        )


async def open_rivalries_hub(interaction: discord.Interaction, cog: BattleCog) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    db = await get_client()
    player_res = (
        await db.table("players")
        .select("manager_name")
        .eq("discord_id", interaction.user.id)
        .maybe_single()
        .execute()
    )
    manager_name = (player_res.data or {}).get("manager_name") or interaction.user.display_name
    try:
        res = await db.rpc("get_manager_rivalries", {"p_owner_id": interaction.user.id}).execute()
        payload = res.data if isinstance(res.data, dict) else {"rivalries": []}
    except Exception as exc:
        await interaction.followup.send(embed=error_embed(api_error_message(exc)), ephemeral=True)
        return
    rivals = payload.get("rivalries") or []
    embed = rivalries_list_embed(payload, manager_name=manager_name)
    view = RivalriesHubView(cog, interaction.user.id, interaction.guild_id or 0, rivals)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
