# apps/discord_bot/core/thread_manager.py
from __future__ import annotations
import asyncio
import logging
import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

class ThreadManager:
    """
    Manages the creation, UI dispatch, and safe cleanup of onboarding threads.
    """
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def create_onboarding_thread(
        self,
        interaction: discord.Interaction,
        owner_id: int,
    ) -> discord.Thread:
        """
        Creates a private thread (or public fallback) off the invocation channel.
        """
        channel = interaction.channel
        if not channel:
            raise ValueError("Interaction channel is not available.")

        # Prefer private thread; fall back to public if guild lacks PRIVATE_THREADS or channel is not a TextChannel
        thread_type = discord.ChannelType.private_thread
        if not isinstance(channel, discord.TextChannel) or \
           "PRIVATE_THREADS" not in (interaction.guild.features if interaction.guild else []):
            thread_type = discord.ChannelType.public_thread

        thread: discord.Thread = await channel.create_thread(
            name=f"⚽ ElevenBoss — Welcome, {interaction.user.display_name}!",
            type=thread_type,
            auto_archive_duration=60,
            reason=f"ElevenBoss onboarding wizard for {interaction.user.name}",
        )
        return thread

    async def delete_thread_after(
        self,
        thread: discord.Thread,
        delay_seconds: int,
        *,
        countdown_message: discord.Message | None = None,
    ) -> None:
        """
        Waits delay_seconds, then deletes the thread. Optionally edits
        countdown_message to display a live countdown before deletion.
        """
        if countdown_message and delay_seconds > 0:
            for remaining in range(delay_seconds, 0, -1):
                try:
                    await countdown_message.edit(
                        content=f"🕐 This setup room closes in **{remaining}s**..."
                    )
                    await asyncio.sleep(1)
                except discord.HTTPException:
                    break
        else:
            await asyncio.sleep(delay_seconds)

        try:
            await thread.delete()
        except discord.HTTPException as e:
            logger.warning(f"Failed to delete onboarding thread {thread.id}: {e}")

    def check_owner(self, interaction: discord.Interaction, owner_id: int) -> bool:
        """Returns True if interaction.user.id == owner_id."""
        return interaction.user.id == owner_id
