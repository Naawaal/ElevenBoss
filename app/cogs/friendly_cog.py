import logging
import discord
from discord import app_commands
from discord.ext import commands

from app.ui.handlers.friendly_handler import (
    handle_friendly_challenge,
    handle_friendly_practice,
)
from app.error_reporting import capture_exception

logger = logging.getLogger("app.cogs.friendly_cog")

@app_commands.guild_only()
class FriendlyGroup(commands.GroupCog, name="friendly"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(
        name="challenge",
        description="Challenge another manager in the server to a friendly match."
    )
    @app_commands.describe(opponent="The server member you want to challenge.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def challenge_command(
        self,
        interaction: discord.Interaction,
        opponent: discord.Member
    ):
        if not interaction.guild_id:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.", ephemeral=True
            )
            return

        # Defer non-ephemerally so the challenge invite is visible publicly to the opponent
        await interaction.response.defer(ephemeral=False)

        try:
            view = await handle_friendly_challenge(
                interaction.guild_id,
                interaction.user,
                opponent
            )
            # Edit the deferred message to show the challenge invite view
            await interaction.edit_original_response(view=view)
            
        except ValueError as ve:
            logger.info(
                f"friendly_challenge_rejected: guild_id={interaction.guild_id}, "
                f"user_id={interaction.user.id}, opponent_id={opponent.id}, reason={ve}"
            )
            await interaction.edit_original_response(content=f"❌ {ve}")
        except Exception as e:
            logger.error(
                f"friendly_challenge_error: failed to challenge opponent={opponent.id} for guild_id={interaction.guild_id}: {e}",
                exc_info=e
            )
            capture_exception(e)
            await interaction.edit_original_response(
                content="❌ An unexpected error occurred while creating the friendly match challenge."
            )

    @app_commands.command(
        name="practice",
        description="Play an instant practice friendly match against a training AI bot."
    )
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def practice_command(self, interaction: discord.Interaction):
        if not interaction.guild_id:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.", ephemeral=True
            )
            return

        # Practice menu is private/ephemeral to the command owner
        await interaction.response.defer(ephemeral=True)

        try:
            view = await handle_friendly_practice(
                interaction.guild_id,
                interaction.user
            )
            await interaction.edit_original_response(view=view)
            
        except ValueError as ve:
            logger.info(
                f"friendly_practice_rejected: guild_id={interaction.guild_id}, "
                f"user_id={interaction.user.id}, reason={ve}"
            )
            await interaction.edit_original_response(content=f"❌ {ve}")
        except Exception as e:
            logger.error(
                f"friendly_practice_error: failed to open practice hub for guild_id={interaction.guild_id}: {e}",
                exc_info=e
            )
            capture_exception(e)
            await interaction.edit_original_response(
                content="❌ An unexpected error occurred while loading the practice hub."
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(FriendlyGroup(bot))
