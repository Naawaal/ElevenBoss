# apps/discord_bot/cogs/profile_cog.py
from __future__ import annotations
import logging
import discord
from discord import app_commands
from discord.ext import commands
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed
from energy import minutes_to_full

logger = logging.getLogger(__name__)

class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="profile", description="View your club's profile, record, and resources.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def profile(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            result = await db.table("players").select("*").eq("discord_id", interaction.user.id).maybe_single().execute()
            player = result.data if result else None
            if not player:
                await interaction.followup.send(
                    embed=error_embed("Profile not found despite registration check."),
                    ephemeral=True
                )
                return

            # Compute energy recovery time
            curr_energy = player["energy"]
            max_energy = player["max_energy"]
            min_to_full = minutes_to_full(curr_energy, max_energy, regen_per_tick=2, minutes_per_tick=5)
            
            if min_to_full > 0:
                hours = min_to_full // 60
                mins = min_to_full % 60
                energy_status = f"{curr_energy}/{max_energy} (Full in {hours}h {mins}m)"
            else:
                energy_status = f"{curr_energy}/{max_energy} (Full)"

            # Fetch global divisions sorted by min_lp ascending
            div_res = await db.table("global_divisions").select("*").order("min_lp").execute()
            divisions = div_res.data or []
            
            user_lp = player.get("global_lp", 0)
            
            # Find current division and next division
            current_div = None
            next_div = None
            for idx, div in enumerate(divisions):
                if user_lp >= div["min_lp"]:
                    current_div = div
                    if idx + 1 < len(divisions):
                        next_div = divisions[idx + 1]
                    else:
                        next_div = None
            
            if not current_div:
                current_div = {"name": "Bronze III", "min_lp": 0}
                if len(divisions) > 1:
                    next_div = divisions[1]

            # Generate ASCII progress bar
            bar_len = 10
            if not next_div:
                # Elite ceiling (no next division)
                progress_bar = f"`[{'█' * bar_len}]` **{user_lp} LP** (Max Division)"
            else:
                min_lp = current_div["min_lp"]
                max_lp = next_div["min_lp"]
                range_lp = max_lp - min_lp
                
                # Progress within the current division's band
                progress_lp = user_lp - min_lp
                ratio = max(0.0, min(1.0, progress_lp / range_lp)) if range_lp > 0 else 0.0
                filled = int(ratio * bar_len)
                empty = bar_len - filled
                
                bar_str = f"[{'█' * filled}{'░' * empty}]"
                progress_bar = f"`{bar_str}` **{user_lp}/{max_lp} LP** to {next_div['name']}"

            embed = discord.Embed(
                title=f"🛡️ Club Profile: {player['club_name']}",
                color=0x00FF87
            )
            embed.add_field(name="👔 Manager Name", value=player["manager_name"], inline=True)
            embed.add_field(name="👤 Username", value=interaction.user.name, inline=True)
            embed.add_field(name="🪙 Coins", value=f"{player['coins']} coins", inline=True)
            embed.add_field(name="⚡ Energy Status", value=energy_status, inline=False)
            
            # Global Arena Stats
            embed.add_field(name="🌍 Global Division", value=current_div["name"], inline=True)
            embed.add_field(name="🏆 Global LP Progress", value=progress_bar, inline=False)

            # Weekly League Stats
            embed.add_field(name="⚔️ Server Division", value=player["division"], inline=True)
            embed.add_field(name="📊 Server League Points", value=f"{player['league_points']} pts (GD: {player['goal_difference']})", inline=True)
            
            w, d, l = player["wins"], player["draws"], player["losses"]
            record = f"{w}W - {d}D - {l}L"
            embed.add_field(name="⚽ Match Record", value=f"{record} ({player['matches_played']} played)", inline=True)
            embed.set_footer(text="ElevenBoss Football Manager")

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.exception("Failed to fetch profile.")
            await interaction.followup.send(
                embed=error_embed(f"An error occurred while loading your profile: {str(e)}"),
                ephemeral=True
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProfileCog(bot))
