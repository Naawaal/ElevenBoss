# apps/discord_bot/cogs/gacha_cog.py
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
import discord
from discord import app_commands
from discord.ext import commands

from gacha import generate_pack
from apps.discord_bot.db.client import get_client
from apps.discord_bot.middleware.guard import ensure_registered
from apps.discord_bot.embeds.gacha_embeds import gacha_claim_embed, gacha_cooldown_embed
from apps.discord_bot.embeds.common_embeds import error_embed

logger = logging.getLogger(__name__)

class GachaCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="gacha-claim", description="Claim a free pack of 5 random players every 22 hours.")
    @app_commands.guild_only()
    @app_commands.check(ensure_registered)
    async def gacha_claim(self, interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        try:
            db = await get_client()
            # Fetch player last_claim_at
            result = await db.table("players").select("last_claim_at").eq("discord_id", interaction.user.id).maybe_single().execute()
            player = result.data if result else None
            
            if not player:
                await interaction.followup.send(
                    embed=error_embed("Account not found. Please register first."),
                    ephemeral=True
                )
                return

            now = datetime.now(timezone.utc)
            last_claim_str = player.get("last_claim_at")
            
            # Cooldown validation
            if last_claim_str:
                last_claim = datetime.fromisoformat(last_claim_str.replace("Z", "+00:00"))
                cooldown_delta = timedelta(hours=22)
                elapsed = now - last_claim
                if elapsed < cooldown_delta:
                    remaining_seconds = (cooldown_delta - elapsed).total_seconds()
                    await interaction.followup.send(
                        embed=gacha_cooldown_embed(remaining_seconds),
                        ephemeral=True
                    )
                    return

            # Generate players (pure gacha logic)
            pack = generate_pack(n=5)
            
            # Prepare player cards payload
            cards_payload = [
                {
                    "owner_id": interaction.user.id,
                    "name": p.name,
                    "position": p.position,
                    "rarity": p.rarity,
                    "base_rating": p.base_rating,
                    "overall": p.overall,
                    "pac": p.pac,
                    "sho": p.sho,
                    "pas": p.pas,
                    "dri": p.dri,
                    "def": p.def_stat,
                    "phy": p.phy,
                    "potential": p.potential,
                    "age": p.age
                }
                for p in pack.players
            ]

            # DB Writes: Update last_claim_at and insert cards
            # We run them sequentially; if card insert fails we log.
            await db.table("players").update({"last_claim_at": now.isoformat()}).eq("discord_id", interaction.user.id).execute()
            await db.table("player_cards").insert(cards_payload).execute()

            # Respond with gacha claim embed
            await interaction.followup.send(embed=gacha_claim_embed(pack), ephemeral=True)
            
        except Exception as e:
            logger.exception("Failed to claim daily pack.")
            await interaction.followup.send(
                embed=error_embed(f"An error occurred while claiming your pack: {str(e)}"),
                ephemeral=True
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GachaCog(bot))
