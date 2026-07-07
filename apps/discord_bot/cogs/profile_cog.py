# apps/discord_bot/cogs/profile_cog.py
from __future__ import annotations
import logging
import discord
from discord import app_commands
from discord.ext import commands
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.common_embeds import error_embed
from apps.discord_bot.core.economy_rpc import format_action_energy_status, sync_action_energy

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

            # Sync unified action energy
            energy_row = await sync_action_energy(db, interaction.user.id)
            curr_energy = energy_row.get("action_energy", player.get("action_energy", player.get("energy", 0)))
            max_energy = energy_row.get("max_energy", player.get("max_energy", 100))
            energy_status = format_action_energy_status(curr_energy, max_energy)
            gems = player.get("tokens", 0)

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
            embed.add_field(name="🪙 Coins", value=f"{player['coins']:,} coins", inline=True)
            embed.add_field(name="💎 Gems", value=f"{gems:,}", inline=True)
            embed.add_field(name="⚡ Action Energy", value=energy_status, inline=False)
            
            # Global Arena Stats
            embed.add_field(name="🌍 Global Division", value=current_div["name"], inline=True)
            embed.add_field(name="🏆 Global LP Progress", value=progress_bar, inline=False)

            # Weekly League Stats
            embed.add_field(name="⚔️ Server Division", value=player["division"], inline=True)
            embed.add_field(name="📊 Division Rank Points", value=f"{player['league_points']} pts (GD: {player['goal_difference']})", inline=True)
            embed.add_field(
                name="ℹ️ Division Rank",
                value="Weekly ladder from **bot battles** only. Guild season table is in `/league hub`.",
                inline=False,
            )
            
            w, d, l = player["wins"], player["draws"], player["losses"]
            record = f"{w}W - {d}D - {l}L"
            embed.add_field(name="⚽ Match Record", value=f"{record} ({player['matches_played']} played)", inline=True)

            # Trophy cabinet (US-26)
            hist_res = await db.table("player_league_history").select("*").eq("player_id", interaction.user.id).order("created_at", desc=True).limit(5).execute()
            history = hist_res.data or []
            if history:
                trophy_lines = []
                for h in history:
                    awards = h.get("awards_json") or []
                    award_label = awards[0].get("type", "participant") if awards else "participant"
                    trophy_lines.append(f"Season #{h.get('season_id', '')[:8]}… — **#{h['finish_position']}** ({award_label})")
                embed.add_field(name="🏆 Trophy Cabinet", value="\n".join(trophy_lines), inline=False)

            embed.set_footer(text="Use /store for daily bonus and energy refills")

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.exception("Failed to fetch profile.")
            await interaction.followup.send(
                embed=error_embed(f"An error occurred while loading your profile: {str(e)}"),
                ephemeral=True
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProfileCog(bot))
