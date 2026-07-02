# app/services/league_lifecycle_service.py

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.future import select

from app.db.session import get_session
from app.repositories.league_repository import get_draft_league_by_guild, get_joined_player_user_ids
from app.repositories.club_repository import get_clubs_in_league
from app.services.league_service import start_league, LeagueResult
from app.services.announcement_service import AnnouncementService
from app.models.league import League, LeagueStatus
from app.models.club import Club
from app.models.manager import Manager

logger = logging.getLogger("app.services.league_lifecycle_service")

class LeagueLifecycleService:
    @staticmethod
    async def check_and_trigger_auto_start(guild_id: int | str) -> LeagueResult | None:
        """
        Check if the draft league in a guild satisfies auto-start conditions.
        If yes, trigger start_league and return the result. Otherwise return None.
        """
        try:
            async with get_session() as session:
                league = await get_draft_league_by_guild(session, guild_id)
                if not league or league.status != LeagueStatus.DRAFT:
                    logger.debug(f"lifecycle_check_skipped: no draft league in guild_id={guild_id}")
                    return None

                # If no deadline is set, do nothing
                if not league.registration_deadline_at:
                    logger.debug(f"lifecycle_check_skipped: no registration deadline set for guild_id={guild_id}")
                    return None

                now_utc = datetime.now(timezone.utc)
                
                # Case 1: Deadline has not passed
                if now_utc < league.registration_deadline_at:
                    logger.debug(f"lifecycle_check_skipped: registration deadline not reached for guild_id={guild_id}")
                    return None

                # Deadline has passed! Count human clubs and total clubs
                clubs = await get_clubs_in_league(session, guild_id, league.id)
                human_clubs = [c for c in clubs if not c.is_bot_controlled]
                human_count = len(human_clubs)
                total_count = len(clubs)
                
                # Fetch joined manager user IDs for player notifications
                joined_player_user_ids = await get_joined_player_user_ids(session, league.id)

                league_id = league.id
                league_name = league.name
                auto_start_after_deadline = league.auto_start_after_deadline
                fill_bots_after_deadline = league.fill_bots_after_deadline
                minimum_human_clubs = league.minimum_human_clubs
                target_club_count = league.target_club_count

            # Process Cases
            
            # Case 2: Deadline passed but auto-start is disabled
            if not auto_start_after_deadline:
                reason = "Auto-start is disabled for this league."
                await LeagueLifecycleService.transition_to_review(league_id, reason, guild_id, joined_player_user_ids)
                return LeagueResult(success=False, code="needs_admin_review", message=reason, league_id=league_id, league_name=league_name)

            # Case 3: Deadline passed and not enough humans joined
            if human_count < minimum_human_clubs:
                reason = f"Minimum humans required ({minimum_human_clubs}) not met. Only {human_count} joined."
                await LeagueLifecycleService.transition_to_review(league_id, reason, guild_id, joined_player_user_ids)
                return LeagueResult(success=False, code="needs_admin_review", message=reason, league_id=league_id, league_name=league_name)

            # Case 4: Deadline passed, league is full with humans
            if total_count == target_club_count:
                logger.info(f"lifecycle_check_start: Case 4 (full human) triggered for guild_id={guild_id}")
                result = await start_league(guild_id, force_bot_fill=False)
                return result

            # Case 5: Deadline passed, enough humans, bot fill enabled
            if total_count < target_club_count and fill_bots_after_deadline:
                logger.info(f"lifecycle_check_start: Case 5 (bot fill) triggered for guild_id={guild_id}")
                result = await start_league(guild_id, force_bot_fill=True)
                return result

            # Case 6: Deadline passed, enough humans, bot fill disabled
            if total_count < target_club_count and not fill_bots_after_deadline:
                reason = "League is under-filled and bot filling is disabled."
                await LeagueLifecycleService.transition_to_review(league_id, reason, guild_id, joined_player_user_ids)
                return LeagueResult(success=False, code="needs_admin_review", message=reason, league_id=league_id, league_name=league_name)

            return None

        except Exception as e:
            logger.error(f"lifecycle_check_failed: error during check for guild_id={guild_id}: {e}", exc_info=e)
            from app.error_reporting import capture_exception
            capture_exception(e)
            return None

    @staticmethod
    async def transition_to_review(league_id, reason: str, guild_id: int | str, player_user_ids: list[str | int]) -> None:
        """
        Transition league to NEEDS_ADMIN_REVIEW status. Notify admin, notify joined players, and announce in channel.
        """
        try:
            async with get_session() as session:
                stmt = select(League).where(League.id == league_id).with_for_update()
                res = await session.execute(stmt)
                league = res.scalar_one_or_none()
                if league and league.status == LeagueStatus.DRAFT:
                    league.status = LeagueStatus.NEEDS_ADMIN_REVIEW
                    league.review_reason = reason
                    await session.commit()
                    logger.info(f"league_moved_to_review: league_id={league_id}, reason={reason}")
                    
                    # 1. Notify Guild Owner/Admin
                    admin_message = (
                        f"🛡️ **ElevenBoss Admin Alert**\n\n"
                        f"The league **{league.name}** in your server requires your review.\n"
                        f"**Reason:** {reason}\n\n"
                        f"Please DM me `/admin` and select the server to resolve this (Extend Deadline, Force Start, or Cancel)."
                    )
                    await AnnouncementService.notify_guild_admin_dm(guild_id, admin_message)

                    # 2. Notify Joined Players
                    player_message = (
                        f"⚠️ **League Registration Update**\n\n"
                        f"The league did not reach the required registration conditions before the deadline. "
                        f"An admin has been notified."
                    )
                    await AnnouncementService.notify_users_dm(player_user_ids, player_message)

                    # 3. Public Game Channel Announcement
                    public_message = (
                        f"⚠️ **League Registration Closed — Pending Admin Review**\n\n"
                        f"The registration deadline has passed but the league requires administrative review before starting. "
                        f"Server administrators have been notified."
                    )
                    await AnnouncementService.send_announcement(guild_id, public_message)
                else:
                    logger.warning(f"league_transition_to_review_skipped: league_id={league_id} not in DRAFT status")
        except Exception as e:
            logger.error(f"league_transition_to_review_failed: league_id={league_id}, error={e}", exc_info=e)
