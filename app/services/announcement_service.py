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
    async def send_announcement_v2(cls, guild_id: int | str, view: discord.ui.View) -> bool:
        """
        Sends an announcement with a V2View payload to the guild's configured results/game channel.
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

            # Send V2View message
            await channel.send(view=view)
            logger.info(f"announcement_v2_sent: guild_id={guild_id}, channel_id={channel_id}")
            return True
        except Exception as e:
            logger.error(f"announcement_failed: failed to send V2 announcement for guild_id={guild_id}: {e}", exc_info=e)
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
        msg += "\n📈 League standings have been updated. Click the buttons below to view updated stats!"

        # Build V2View with buttons
        from app.ui.components import container, text_display, action_row, secondary_button, V2View
        from app.ui.custom_ids import encode_custom_id

        # Use "_" as nonce for public buttons (auto-defection handled on-click)
        table_id = encode_custom_id("league", "view_table", "main", "_")
        fixtures_id = encode_custom_id("fixtures", "view", "current", "_")
        recent_id = encode_custom_id("match", "recent", "main", "_")

        view = V2View([
            container([
                text_display(msg)
            ]),
            action_row([
                secondary_button("📈 View Table", table_id),
                secondary_button("📅 View Fixtures", fixtures_id),
                secondary_button("⚽ View Recent Match", recent_id)
            ])
        ])

        return await cls.send_announcement_v2(guild_id, view)

    @classmethod
    async def announce_season_complete(cls, guild_id: int | str, season_number: int, winner_name: str | None = None) -> bool:
        msg = (
            f"🏁 **SEASON {season_number} COMPLETED!**\n\n"
            f"The final week has been simulated and the season is officially over. "
        )
        if winner_name:
            msg += f"Congratulations to our champions, **{winner_name}**! 🏆\n\n"
        else:
            msg += "Congratulations to everyone on finishing the season!\n\n"
        msg += "📈 The final standings table is now available. Click below to view the final table."

        # Build V2View with button
        from app.ui.components import container, text_display, action_row, secondary_button, V2View
        from app.ui.custom_ids import encode_custom_id

        table_id = encode_custom_id("league", "view_table", "main", "_")
        view = V2View([
            container([
                text_display(msg)
            ]),
            action_row([
                secondary_button("🏆 View Final Table", table_id)
            ])
        ])

        return await cls.send_announcement_v2(guild_id, view)

    @classmethod
    async def notify_users_dm(cls, user_ids: list[str | int], message: str) -> None:
        """
        Send direct messages to list of user IDs. Logs failure safely.
        """
        if cls.bot is None:
            logger.error("bot instance not set on AnnouncementService")
            return
        for u_id in user_ids:
            try:
                user = cls.bot.get_user(int(u_id))
                if not user:
                    user = await cls.bot.fetch_user(int(u_id))
                if user:
                    await user.send(message)
                    logger.info(f"DM notification sent to user {u_id}")
            except Exception as e:
                logger.warning(f"Failed to DM user {u_id}: {e}")

    @classmethod
    async def notify_guild_admin_dm(cls, guild_id: int | str, message: str) -> None:
        """
        Send direct message to the owner of the guild. Logs failure safely.
        """
        if cls.bot is None:
            logger.error("bot instance not set on AnnouncementService")
            return
        try:
            guild = cls.bot.get_guild(int(guild_id))
            if not guild:
                guild = await cls.bot.fetch_guild(int(guild_id))
            if guild and guild.owner_id:
                owner = cls.bot.get_user(guild.owner_id)
                if not owner:
                    owner = await cls.bot.fetch_user(guild.owner_id)
                if owner:
                    await owner.send(message)
                    logger.info(f"DM notification sent to guild owner/admin {guild.owner_id}")
        except Exception as e:
            logger.warning(f"Failed to DM guild owner/admin for guild {guild_id}: {e}")
