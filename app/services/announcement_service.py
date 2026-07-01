# app/services/announcement_service.py

import logging
import discord
from app.db.session import get_session
from app.repositories.guild_config_repository import get_or_create_guild_config

logger = logging.getLogger("app.services.announcement_service")

class AnnouncementService:
    bot: discord.Client | None = None

    @classmethod
    async def send_announcement(cls, guild_id: int | str, message: str) -> bool:
        """
        Sends an announcement message to the guild's configured game_channel or announcement_channel.
        Returns True if successful, False otherwise. Does not raise exceptions.
        """
        if cls.bot is None:
            logger.error(f"announcement_failed: bot instance not set on AnnouncementService, guild_id={guild_id}")
            return False

        try:
            guild = cls.bot.get_guild(int(guild_id))
            if not guild:
                guild = await cls.bot.fetch_guild(int(guild_id))
            
            if not guild:
                logger.error(f"announcement_failed: guild not found, guild_id={guild_id}")
                return False

            # Get guild config for game channel
            async with get_session() as session:
                config = await get_or_create_guild_config(session, guild_id)
                channel_id = config.matchday_announcement_channel_id or config.game_channel_id

            if not channel_id:
                logger.warning(f"announcement_skipped: no channel configured for guild_id={guild_id}")
                return False

            channel = guild.get_channel(int(channel_id))
            if not channel:
                channel = await guild.fetch_channel(int(channel_id))

            if not channel:
                logger.error(f"announcement_failed: channel not found, channel_id={channel_id}, guild_id={guild_id}")
                return False

            # Send message
            await channel.send(message)
            logger.info(f"announcement_sent: guild_id={guild_id}, channel_id={channel_id}")
            return True
        except Exception as e:
            logger.error(f"announcement_failed: failed to send announcement for guild_id={guild_id}: {e}", exc_info=e)
            return False

    @classmethod
    async def announce_league_start(cls, guild_id: int | str, league_name: str) -> bool:
        msg = f"🏆 **LEAGUE STARTED!**\n\nThe draft league **{league_name}** has officially started! Season 1 is now active. Matches have been scheduled. Use `/fixtures` to view the schedule!"
        return await cls.send_announcement(guild_id, msg)

    @classmethod
    async def announce_season_start(cls, guild_id: int | str, season_number: int) -> bool:
        msg = f"⚽ **SEASON {season_number} HAS BEGUN!**\n\nThe new season is underway. Lineups are locked for matches. Good luck to all managers!"
        return await cls.send_announcement(guild_id, msg)

    @classmethod
    async def announce_matchday_summary(cls, guild_id: int | str, week: int, results: list) -> bool:
        msg = f"⚡ **WEEK {week} MATCHDAY RESULTS**\n\n"
        for r in results:
            msg += f"• **{r.home_club_name}** {r.home_goals}–{r.away_goals} **{r.away_club_name}**\n"
        msg += "\n📈 League standings have been updated. Use `/table` to view the updated standings!"
        return await cls.send_announcement(guild_id, msg)

    @classmethod
    async def announce_season_complete(cls, guild_id: int | str, season_number: int, winner_name: str | None = None) -> bool:
        msg = f"🏁 **SEASON {season_number} COMPLETED!**\n\nThe final week has been simulated and the season is officially over. "
        if winner_name:
            msg += f"Congratulations to our champions, **{winner_name}**! 🏆"
        else:
            msg += "Congratulations to everyone on finishing the season!"
        return await cls.send_announcement(guild_id, msg)
