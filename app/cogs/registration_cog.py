import logging
import discord
from discord import app_commands
from discord.ext import commands
from app.services.registration_service import register_club, validate_club_name
from app.ui.embeds import registration_success_embed

logger = logging.getLogger("app.cogs.registration_cog")

class RegistrationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="register", description="Register a new football club and receive a squad of 25 players.")
    @app_commands.describe(club_name="The name of your new football club (3-32 characters).")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def register(self, interaction: discord.Interaction, club_name: str):
        # Must be run inside a guild
        if not interaction.guild_id:
            await interaction.response.send_message("❌ This command can only be used within a server.", ephemeral=True)
            return

        # Perform synchronous pre-validation to avoid DB hits
        try:
            validate_club_name(club_name)
        except ValueError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
            return

        # Defer ephemerally to prevent slash command timeouts
        await interaction.response.defer(ephemeral=True)

        # Call registration service
        result = await register_club(
            guild_id=interaction.guild_id,
            discord_user_id=interaction.user.id,
            club_name=club_name
        )

        if not result.success:
            await interaction.edit_original_response(content=f"❌ {result.message}")
            return

        # Success message
        await interaction.edit_original_response(content="✅ Club registration complete!")
        
        # Send public success embed
        embed = registration_success_embed(
            club_name=result.club_name,
            manager_mention=interaction.user.mention,
            squad_size=result.squad_size,
            avg_ovr=result.average_overall,
            budget=result.budget
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(RegistrationCog(bot))
