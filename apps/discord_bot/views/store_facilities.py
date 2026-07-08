# apps/discord_bot/views/store_facilities.py
"""Club Facilities sub-hub under /store (Phase C)."""
from __future__ import annotations

from datetime import datetime, timezone

import discord

from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from apps.discord_bot.core.view_helpers import disable_view_on_timeout, set_view_controls_disabled
from economy import (
    FACILITY_MAX_LEVEL,
    facility_label,
    facility_upgrade_cost,
    min_matches_for_next_level,
    training_ground_drill_xp_bonus,
    youth_academy_tier,
)


def _upgrade_blocked_reason(player: dict, facility_key: str) -> str | None:
    level = int(
        player.get("youth_academy_level" if facility_key == "youth_academy" else "training_ground_level", 1)
    )
    if level >= FACILITY_MAX_LEVEL:
        return "Max level reached."
    cost = facility_upgrade_cost(level)
    if cost is None:
        return "Cannot upgrade."
    if int(player.get("coins", 0)) < cost:
        return f"Need 🪙 {cost:,} coins."
    next_level = level + 1
    need_matches = min_matches_for_next_level(level)
    if need_matches and int(player.get("matches_played", 0)) < need_matches:
        return f"Requires {need_matches} career matches for L{next_level}."
    last_up = player.get("facility_last_upgrade_at")
    if last_up:
        try:
            ts = datetime.fromisoformat(str(last_up).replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - ts).days < 7:
                return "Weekly upgrade cooldown (1 per UTC week)."
        except ValueError:
            pass
    return None


def facilities_embed(player: dict) -> discord.Embed:
    youth_lv = int(player.get("youth_academy_level", 1))
    tg_lv = int(player.get("training_ground_level", 1))
    youth_tier = youth_academy_tier(youth_lv)
    tg_bonus = training_ground_drill_xp_bonus(tg_lv)

def _next_upgrade_line(player: dict, facility_key: str) -> str:
    level_key = "youth_academy_level" if facility_key == "youth_academy" else "training_ground_level"
    level = int(player.get(level_key, 1))
    if level >= FACILITY_MAX_LEVEL:
        return "✅ **Max level**"
    cost = facility_upgrade_cost(level)
    need = min_matches_for_next_level(level)
    line = f"Next: **L{level + 1}** — 🪙 **{cost:,}** coins"
    if need:
        line += f" · **{need}+** career matches"
    block = _upgrade_blocked_reason(player, facility_key)
    if block:
        line += f"\n⚠️ {block}"
    return line

    embed = discord.Embed(
        title="🏗️ Club Facilities",
        description=(
            "Optional long-term coin investments. **Level 1 is free for everyone** — "
            "upgrades improve future youth intake and drill XP.\n\n"
            f"🪙 **Balance**: `{int(player.get('coins', 0)):,}` coins"
        ),
        color=0x00FF87,
    )
    embed.add_field(
        name=f"🌱 Youth Academy — Level {youth_lv}/{FACILITY_MAX_LEVEL}",
        value=(
            f"Intake POT cap **{youth_tier.pot_max}** · OVR **{youth_tier.ovr_min}–{youth_tier.ovr_max}** · "
            f"Gem chance **{int(youth_tier.gem_chance * 100)}%**\n"
            + _next_upgrade_line(player, "youth_academy")
        ),
        inline=False,
    )
    embed.add_field(
        name=f"🏋️ Training Ground — Level {tg_lv}/{FACILITY_MAX_LEVEL}",
        value=(
            f"Drill XP bonus **+{tg_bonus}** per drill (L1 = today)\n"
            + _next_upgrade_line(player, "training_ground")
        ),
        inline=False,
    )
    return embed


class FacilitiesHubView(discord.ui.View):
    def __init__(self, owner_id: int, player: dict) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.player = player

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This belongs to another manager.", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.primary, label="⬆️ Upgrade Youth Academy", row=0)
    async def upgrade_youth(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await self._upgrade(interaction, "youth_academy")

    @discord.ui.button(style=discord.ButtonStyle.primary, label="⬆️ Upgrade Training Ground", row=0)
    async def upgrade_training(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await self._upgrade(interaction, "training_ground")

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="⬅️ Back to Store", row=1)
    async def back(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        from apps.discord_bot.cogs.store_cog import show_store
        await show_store(interaction, self.owner_id)

    async def _upgrade(self, interaction: discord.Interaction, facility_key: str) -> None:
        await interaction.response.defer(ephemeral=True)
        set_view_controls_disabled(self, disabled=True)
        level = int(
            self.player.get("youth_academy_level" if facility_key == "youth_academy" else "training_ground_level", 1)
        )
        cost = facility_upgrade_cost(level)
        block = _upgrade_blocked_reason(self.player, facility_key)
        if block:
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(embed=error_embed(block), ephemeral=True)
            return
        try:
            db = await get_client()
            res = await db.rpc("upgrade_club_facility", {
                "p_owner_id": self.owner_id,
                "p_facility_key": facility_key,
                "p_expected_cost": cost,
            }).execute()
            data = res.data or {}
            label = facility_label(facility_key)
            await interaction.followup.send(
                embed=success_embed(
                    f"**{label}** upgraded to **Level {data.get('new_level', level + 1)}** "
                    f"for **🪙 {data.get('coins_spent', cost):,}** coins."
                ),
                ephemeral=True,
            )
            player_res = await db.table("players").select("*").eq("discord_id", self.owner_id).maybe_single().execute()
            self.player = player_res.data or self.player
            embed = facilities_embed(self.player)
            view = FacilitiesHubView(self.owner_id, self.player)
            if interaction.message:
                await interaction.message.edit(embed=embed, view=view)
        except Exception as exc:
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)


async def show_facilities(interaction: discord.Interaction, owner_id: int) -> None:
    db = await get_client()
    player_res = await db.table("players").select("*").eq("discord_id", owner_id).maybe_single().execute()
    player = player_res.data
    if not player:
        await interaction.followup.send(embed=error_embed("Player profile not found."), ephemeral=True)
        return
    embed = facilities_embed(player)
    view = FacilitiesHubView(owner_id, player)
    if interaction.response.is_done():
        if interaction.message:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.edit_message(embed=embed, view=view)
