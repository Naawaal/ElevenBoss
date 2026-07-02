"""
OnboardingThreadFactory — creates Discord threads for the onboarding flow.
Tries private first, falls back to public. Persists the capability to guild_config.
"""
import logging
from dataclasses import dataclass
from typing import Literal
import discord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from app.models.guild_config import GuildConfig

logger = logging.getLogger("app.services.onboarding_thread_factory")


@dataclass
class OnboardingThreadResult:
    thread: discord.Thread
    thread_id: int
    channel_id: int
    starter_message_id: int | None
    mode: Literal["PRIVATE", "PUBLIC"]
    # Non-None when mode=="PUBLIC" — text to send as a warning in the thread
    visibility_warning: str | None


async def create_onboarding_thread(
    interaction: discord.Interaction,
    session: AsyncSession,
    guild_config: GuildConfig,
) -> OnboardingThreadResult:
    """
    Attempt to create a private thread in the interaction channel.
    If the bot lacks permission or private threads are disabled for the guild,
    fall back to a public thread and update the guild_config cache.
    """
    channel = interaction.channel
    user = interaction.user

    if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
        # Fallback: use the guild's default channel
        channel = interaction.guild.system_channel or interaction.guild.text_channels[0]

    # Check if we already know private threads don't work
    use_private = guild_config.supports_private_threads is not False

    if use_private:
        try:
            thread = await channel.create_thread(
                name=f"⚽ Registration — {user.display_name}",
                type=discord.ChannelType.private_thread,
                invitable=False,
                reason="ElevenBoss onboarding session",
            )
            # Cache the success
            await _update_private_thread_support(session, guild_config.guild_id, True)
            logger.info(
                f"onboarding_thread_created: private, thread_id={thread.id}, user={user.id}"
            )
            return OnboardingThreadResult(
                thread=thread,
                thread_id=thread.id,
                channel_id=channel.id,
                starter_message_id=None,
                mode="PRIVATE",
                visibility_warning=None,
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            logger.warning(
                f"Private thread creation failed (guild={interaction.guild_id}): {e}. "
                "Falling back to public thread."
            )
            # Cache the failure so we don't retry
            await _update_private_thread_support(session, guild_config.guild_id, False)

    # Public thread fallback: send a starter message first, then thread from it
    try:
        starter_msg = await channel.send(
            f"📋 Setting up **{user.display_name}'s** club registration..."
        )
        thread = await starter_msg.create_thread(
            name=f"⚽ Registration — {user.display_name}",
            reason="ElevenBoss onboarding session",
        )
        logger.info(
            f"onboarding_thread_created: public, thread_id={thread.id}, user={user.id}"
        )
        visibility_warning = (
            "⚠️ **Note**: This server doesn't support private threads, so your registration "
            "setup is visible to other members. This doesn't affect your club in any way!"
        )
        return OnboardingThreadResult(
            thread=thread,
            thread_id=thread.id,
            channel_id=channel.id,
            starter_message_id=starter_msg.id,
            mode="PUBLIC",
            visibility_warning=visibility_warning,
        )
    except (discord.Forbidden, discord.HTTPException) as e:
        logger.error(f"Public thread creation also failed: {e}")
        raise RuntimeError(
            "I couldn't create a setup thread in this channel. "
            "Please make sure I have **Manage Threads** and **Create Public Threads** permissions."
        ) from e


async def _update_private_thread_support(
    session: AsyncSession, guild_id: str, supports: bool
) -> None:
    """Persist the private-thread capability result to guild_config."""
    try:
        stmt = (
            update(GuildConfig)
            .where(GuildConfig.guild_id == str(guild_id))
            .values(supports_private_threads=supports)
        )
        await session.execute(stmt)
    except Exception as e:
        logger.warning(f"Could not update supports_private_threads for guild {guild_id}: {e}")
