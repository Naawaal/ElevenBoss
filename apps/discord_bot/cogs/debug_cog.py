from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from apps.discord_bot.db.client import get_client
from apps.discord_bot.embeds.common_embeds import error_embed
from apps.discord_bot.core.economy_rpc import (
    get_game_config_int,
    match_energy_cost,
    sync_action_energy,
    economy_v2_enabled,
)


async def is_owner(interaction: discord.Interaction) -> bool:
    return await interaction.client.is_owner(interaction.user)


class DebugCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    debug_group = app_commands.Group(name="debug", description="Owner-only debugging tools.", guild_only=True)

    @debug_group.command(name="energy", description="Inspect energy/XP tuning values and simulate regen.")
    @app_commands.check(is_owner)
    @app_commands.describe(
        target="Optional manager to inspect (defaults to you).",
        minutes="Simulated minutes of regen.",
        current_energy="Override current energy for simulation (optional).",
    )
    async def debug_energy(
        self,
        interaction: discord.Interaction,
        target: discord.User | None = None,
        minutes: app_commands.Range[int, 0, 10080] = 60,
        current_energy: app_commands.Range[int, 0, 1000] | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            who = target or interaction.user

            v2 = await economy_v2_enabled(db)
            energy_row = await sync_action_energy(db, int(who.id))
            ae = int(energy_row.get("action_energy") or 0)
            max_e = int(energy_row.get("max_energy") or 100)
            regen_per_min = float(energy_row.get("regen_per_min") or (1 / 6))

            # Config-driven costs (fallback to code defaults).
            bot_cost = await get_game_config_int(db, "match_energy_bot", match_energy_cost("bot", v2=v2))
            league_cost = await get_game_config_int(db, "match_energy_league", match_energy_cost("league", v2=v2))
            friendly_cost = await get_game_config_int(db, "match_energy_friendly", match_energy_cost("friendly", v2=v2))
            basic_drill_energy = await get_game_config_int(db, "drill_basic_energy", 10)
            adv_drill_energy = await get_game_config_int(db, "drill_advanced_energy", 15)
            energy_refill_amt = await get_game_config_int(db, "energy_refill_amount", 50)

            # XP bases (drills).
            basic_drill_xp = await get_game_config_int(db, "drill_basic_xp", 30)
            adv_drill_xp = await get_game_config_int(db, "drill_advanced_xp", 80)

            # Evolution pacing.
            evo_cd_h = await get_game_config_int(db, "evolution_cooldown_hours", 10)
            evo_slots = await get_game_config_int(db, "evolution_max_active", 3)

            # Derived regen math (keep it consistent with SQL floor()).
            sim_start = ae if current_energy is None else int(current_energy)
            sim_regen = int((minutes or 0) * regen_per_min) if regen_per_min > 0 else 0
            sim_end = min(max_e, sim_start + sim_regen)

            embed = discord.Embed(
                title="🧪 Debug: Energy & Progression Tunables",
                description=f"Target: {who.mention}",
                color=0x5865F2,
            )
            embed.add_field(
                name="Energy",
                value=(
                    f"⚡ Current: **{ae}/{max_e}**\n"
                    f"🔁 Regen: **{regen_per_min:.4f} per min** (~{int(round(1/regen_per_min))} min / energy)\n"
                    f"🧪 Sim: start **{sim_start}** +{minutes}m → regen **+{sim_regen}** → **{sim_end}/{max_e}**"
                ),
                inline=False,
            )
            embed.add_field(
                name="Energy Costs",
                value=(
                    f"🤖 Bot battle: **{bot_cost}**\n"
                    f"🏆 League match: **{league_cost}**\n"
                    f"🤝 Friendly match: **{friendly_cost}**\n"
                    f"🏋️ Drill (basic/adv): **{basic_drill_energy}/{adv_drill_energy}**"
                ),
                inline=True,
            )
            embed.add_field(
                name="XP Bases",
                value=f"🏋️ Drill XP (basic/adv): **{basic_drill_xp}/{adv_drill_xp}**",
                inline=True,
            )
            embed.add_field(
                name="Evolution pacing",
                value=f"🧬 Cooldown: **{evo_cd_h}h** · Slots: **{evo_slots}**",
                inline=True,
            )
            embed.add_field(
                name="Refill",
                value=f"⚡ +{energy_refill_amt} energy (max 3/day via RPC)",
                inline=True,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DebugCog(bot))

