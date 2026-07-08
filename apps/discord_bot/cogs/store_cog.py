# apps/discord_bot/cogs/store_cog.py
"""Club store hub — daily login bonus and energy refills (US-25)."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed, success_embed
from apps.discord_bot.embeds.gacha_embeds import gacha_cooldown_embed, gacha_claim_embed
from apps.discord_bot.core.economy_rpc import format_action_energy_status, sync_action_energy
from apps.discord_bot.core.view_helpers import disable_view_on_timeout, set_view_controls_disabled
from apps.discord_bot.core.card_payload import card_rpc_payload
from gacha import generate_pack


async def show_store(interaction: discord.Interaction, owner_id: int) -> None:
    db = await get_client()
    player_res = await db.table("players").select("*").eq("discord_id", owner_id).maybe_single().execute()
    player = player_res.data if player_res else None
    if not player:
        await interaction.followup.send(embed=error_embed("Player profile not found."), ephemeral=True)
        return

    energy_row = await sync_action_energy(db, owner_id)
    ae = energy_row.get("action_energy", 0)
    max_e = energy_row.get("max_energy", 100)
    gems = player.get("tokens", 0)
    streak = player.get("login_streak", 0)
    last_login = player.get("last_daily_login")
    login_claimed_today = last_login is not None and str(last_login) == str(date.today())

    last_claim_str = player.get("last_claim_at")
    gacha_ready = True
    gacha_cooldown_str = ""
    if last_claim_str:
        try:
            last_claim = datetime.fromisoformat(last_claim_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            cooldown_delta = timedelta(hours=22)
            elapsed = now - last_claim
            if elapsed < cooldown_delta:
                gacha_ready = False
                remaining_seconds = (cooldown_delta - elapsed).total_seconds()
                hours = int(remaining_seconds // 3600)
                minutes = int((remaining_seconds % 3600) // 60)
                gacha_cooldown_str = f"{hours}h {minutes}m"
        except Exception:
            logger.exception("Failed to parse last_claim_at.")

    embed = discord.Embed(
        title="🏪 Club Store",
        description=(
            "Claim your daily bonus and purchase action energy refills.\n\n"
            f"🪙 **Coins**: `{player['coins']:,}`\n"
            f"💎 **Gems**: `{gems:,}`\n"
            f"{format_action_energy_status(ae, max_e)}"
        ),
        color=0x00FF87,
    )
    embed.add_field(
        name="🎁 Daily Login Bonus",
        value=(
            "Once per UTC day. Streak bonus up to +50 coins.\n"
            + ("✅ Claimed today." if login_claimed_today else f"Current streak: **{streak or 0}** day(s).")
        ),
        inline=False,
    )
    embed.add_field(
        name="⚡ Energy Refill",
        value="+50 action energy. Costs **200 / 400 / 600** coins (1st–3rd refill per day).",
        inline=False,
    )
    embed.add_field(
        name="🎫 Daily Gacha Pack",
        value=(
            "Claim a free pack of 5 random players. Claimable every 22 hours.\n"
            + ("🟢 Available now!" if gacha_ready else f"⏳ Cooldown: **{gacha_cooldown_str}** remaining.")
        ),
        inline=False,
    )
    embed.add_field(
        name="🏗️ Club Facilities",
        value="Upgrade Youth Academy (intake quality) and Training Ground (drill XP bonus).",
        inline=False,
    )

    view = StoreHubView(owner_id, login_claimed_today=login_claimed_today, gacha_ready=gacha_ready)
    if interaction.response.is_done():
        if interaction.message is not None:
            try:
                await interaction.followup.edit_message(interaction.message.id, embed=embed, view=view)
            except discord.NotFound:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class StoreHubView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        *,
        login_claimed_today: bool = False,
        gacha_ready: bool = True,
    ) -> None:
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self._sync_button_states(login_claimed_today, gacha_ready)

    def _sync_button_states(self, login_claimed_today: bool, gacha_ready: bool) -> None:
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if child.custom_id == "store_daily_login":
                child.disabled = login_claimed_today
            elif child.custom_id == "store_gacha_claim":
                child.disabled = not gacha_ready

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This store belongs to another manager.", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.success, label="🎁 Claim Daily Login", custom_id="store_daily_login", row=0)
    async def daily_login_btn(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        set_view_controls_disabled(self, disabled=True)
        try:
            db = await get_client()
            res = await db.rpc("claim_daily_login", {"p_club_id": self.owner_id}).execute()
            data = res.data or {}
            reward = data.get("reward", data.get("coin_delta", 0))
            streak = data.get("streak", 1)
            await interaction.followup.send(
                embed=success_embed(f"Daily bonus: **+{reward}** coins (streak **{streak}** days)."),
                ephemeral=True,
            )
            await show_store(interaction, self.owner_id)
        except Exception as exc:
            err = str(exc)
            if "already claimed today" in err.lower():
                await interaction.followup.send(
                    embed=error_embed("You've already claimed your daily login bonus today."),
                    ephemeral=True,
                )
                await show_store(interaction, self.owner_id)
                return
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(embed=error_embed(err), ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.primary, label="⚡ Buy Energy Refill", custom_id="store_energy_refill", row=0)
    async def energy_refill_btn(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        set_view_controls_disabled(self, disabled=True)
        try:
            db = await get_client()
            res = await db.rpc("purchase_energy_refill", {"p_club_id": self.owner_id}).execute()
            data = res.data or {}
            await interaction.followup.send(
                embed=success_embed(
                    f"Refilled energy. Balance: **{data.get('action_energy', '?')}/{data.get('max_energy', 100)}**"
                ),
                ephemeral=True,
            )
            await show_store(interaction, self.owner_id)
        except Exception as exc:
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.secondary, label="🎫 Claim Free Pack", custom_id="store_gacha_claim", row=0)
    async def gacha_claim_btn(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        set_view_controls_disabled(self, disabled=True)
        try:
            db = await get_client()
            pack = generate_pack(n=5)
            cards_payload = [card_rpc_payload(p) for p in pack.players]

            await db.rpc("claim_daily_pack", {
                "p_club_id": self.owner_id,
                "p_cards": cards_payload,
            }).execute()

            await interaction.followup.send(embed=gacha_claim_embed(pack), ephemeral=True)
            await show_store(interaction, self.owner_id)

        except Exception as exc:
            err = str(exc)
            if "COOLDOWN:" in err:
                try:
                    remaining = int(err.split("COOLDOWN:")[-1].strip())
                    await interaction.followup.send(embed=gacha_cooldown_embed(remaining), ephemeral=True)
                    await show_store(interaction, self.owner_id)
                    return
                except ValueError:
                    pass
            logger.exception("Failed to claim daily pack in store.")
            set_view_controls_disabled(self, disabled=False)
            await interaction.followup.send(
                embed=error_embed(f"An error occurred while claiming your pack: {err}"),
                ephemeral=True,
            )

    @discord.ui.button(style=discord.ButtonStyle.primary, label="🏗️ Club Facilities", custom_id="store_facilities", row=1)
    async def facilities_btn(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        from apps.discord_bot.views.store_facilities import show_facilities
        await show_facilities(interaction, self.owner_id)

    async def on_timeout(self) -> None:
        await disable_view_on_timeout(self)


class StoreCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="store", description="Club store: daily login bonus and energy refills.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def store(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            await show_store(interaction, interaction.user.id)
        except Exception as e:
            logger.exception("Failed to open store.")
            await interaction.followup.send(embed=error_embed(str(e)), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StoreCog(bot))
